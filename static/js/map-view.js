/**
 * Harbor — Interactive Mapbox GL JS map view
 *
 * Displays a choropleth of state municipalities coloured by
 * grant award metrics (total funding or award count).  Data is fetched
 * from the Django MapDataAPIView endpoint and joined with GeoJSON features.
 */
(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------
    const GEOJSON_URL = '/static/data/ct-towns.geojson';
    const API_URL     = '/auth/api/map-data/';

    const COLOR_RAMP = [
        '#f7fbff',
        '#deebf7',
        '#c6dbef',
        '#9ecae1',
        '#6baed6',
        '#4292c6',
        '#2171b5',
        '#084594',
    ];

    const CT_CENTER  = [-72.699, 41.6032];
    const CT_ZOOM    = 8;
    const CT_BOUNDS  = [[-73.73, 40.95], [-71.78, 42.06]];

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    /** Format a number as US currency (no decimals). */
    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0,
        }).format(amount);
    }

    /** Compact currency display for legend labels. */
    function formatCompact(num) {
        if (num >= 1e9) return '$' + (num / 1e9).toFixed(1) + 'B';
        if (num >= 1e6) return '$' + (num / 1e6).toFixed(1) + 'M';
        if (num >= 1e3) return '$' + (num / 1e3).toFixed(0) + 'K';
        return '$' + num;
    }

    /** Format a number with commas. */
    function formatNumber(num) {
        return new Intl.NumberFormat('en-US').format(num);
    }

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------
    let geojsonData     = null;  // raw GeoJSON FeatureCollection
    let municipalityData = {};   // API response keyed by municipality name
    let currentMetric   = 'total_funding';

    // DOM references
    const metricSelect  = document.getElementById('metric-select');
    const agencySelect  = document.getElementById('agency-select');
    const programSelect = document.getElementById('program-select');
    const townSelect    = document.getElementById('town-select');
    const resetBtn      = document.getElementById('reset-filters');
    const legendTitle   = document.getElementById('legend-title');
    const legendItems   = document.getElementById('legend-items');
    const hoverTooltip  = document.getElementById('hover-tooltip');
    const statTowns     = document.getElementById('stat-towns');
    const statAwards    = document.getElementById('stat-awards');
    const statFunding   = document.getElementById('stat-funding');

    // -----------------------------------------------------------------------
    // Map initialisation
    // -----------------------------------------------------------------------
    mapboxgl.accessToken = JSON.parse(
        document.getElementById('mapbox-token').textContent,
    );

    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/light-v11',
        center: CT_CENTER,
        zoom: CT_ZOOM,
        minZoom: 7,
        maxZoom: 14,
        maxBounds: [[-74.5, 40.4], [-71.0, 42.6]],
    });

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    // -----------------------------------------------------------------------
    // Data loading
    // -----------------------------------------------------------------------

    /** Fetch the GeoJSON once and cache it. */
    async function loadGeoJSON() {
        const resp = await fetch(GEOJSON_URL);
        geojsonData = await resp.json();

        // Populate town selector dropdown
        const towns = geojsonData.features
            .map(f => f.properties.Municipality)
            .filter(Boolean)
            .sort();

        towns.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            townSelect.appendChild(opt);
        });
    }

    /** Fetch municipality data from the API, with optional filters. */
    async function loadMapData() {
        const params = new URLSearchParams();
        const agency  = agencySelect.value;
        const program = programSelect.value;
        if (agency)  params.set('agency', agency);
        if (program) params.set('program', program);

        const url  = API_URL + (params.toString() ? '?' + params.toString() : '');
        const resp = await fetch(url);
        const data = await resp.json();
        municipalityData = data.municipalities || {};
    }

    // -----------------------------------------------------------------------
    // GeoJSON + data merge
    // -----------------------------------------------------------------------

    /**
     * Merge API data into GeoJSON properties so Mapbox expressions can read
     * them directly from the source.
     */
    function mergeData() {
        if (!geojsonData) return;

        geojsonData.features.forEach(feature => {
            const name = feature.properties.Municipality;
            const data = municipalityData[name] || {};
            feature.properties._total_funding = data.total_funding || 0;
            feature.properties._award_count   = data.award_count   || 0;
        });
    }

    // -----------------------------------------------------------------------
    // Choropleth rendering
    // -----------------------------------------------------------------------

    /** Compute nice stop values for the current metric. */
    function computeStops() {
        const prop   = '_' + currentMetric;
        const values = geojsonData.features
            .map(f => f.properties[prop])
            .filter(v => v > 0);

        if (values.length === 0) {
            // No data — return minimal stops
            return [0, 1, 2, 3, 4, 5, 6, 7];
        }

        const maxVal = Math.max(...values);
        const stops  = [];
        for (let i = 0; i < 8; i++) {
            stops.push(Math.round((maxVal / 7) * i));
        }
        return stops;
    }

    /** Build a Mapbox interpolate expression for fill-color. */
    function buildColorExpression(stops) {
        const prop = '_' + currentMetric;
        const expr = [
            'interpolate', ['linear'],
            ['coalesce', ['get', prop], 0],
        ];
        for (let i = 0; i < 8; i++) {
            expr.push(stops[i], COLOR_RAMP[i]);
        }
        return expr;
    }

    /** Add or update the choropleth layers on the map. */
    function renderChoropleth() {
        mergeData();

        const stops     = computeStops();
        const fillColor = buildColorExpression(stops);

        if (map.getSource('ct-towns')) {
            // Update existing source data
            map.getSource('ct-towns').setData(geojsonData);
            map.setPaintProperty('ct-towns-fill', 'fill-color', fillColor);
        } else {
            // First render — add source + layers
            map.addSource('ct-towns', {
                type: 'geojson',
                data: geojsonData,
                generateId: true,
            });

            map.addLayer({
                id: 'ct-towns-fill',
                type: 'fill',
                source: 'ct-towns',
                paint: {
                    'fill-color': fillColor,
                    'fill-opacity': 0.8,
                },
            });

            map.addLayer({
                id: 'ct-towns-border',
                type: 'line',
                source: 'ct-towns',
                paint: {
                    'line-color': '#627BC1',
                    'line-width': [
                        'case',
                        ['boolean', ['feature-state', 'hover'], false],
                        2.5,
                        0.6,
                    ],
                    'line-opacity': 0.7,
                },
            });
        }

        updateLegend(stops);
        updateStats();
    }

    // -----------------------------------------------------------------------
    // Legend
    // -----------------------------------------------------------------------
    function updateLegend(stops) {
        const isFunding = currentMetric === 'total_funding';
        legendTitle.textContent = isFunding ? 'Total Funding' : 'Award Count';
        legendItems.innerHTML = '';

        for (let i = 0; i < 8; i++) {
            const row   = document.createElement('div');
            row.className = 'legend-row';

            const swatch = document.createElement('div');
            swatch.className = 'legend-color';
            swatch.style.backgroundColor = COLOR_RAMP[i];

            const label = document.createElement('span');
            if (isFunding) {
                label.textContent = formatCompact(stops[i]);
            } else {
                label.textContent = formatNumber(stops[i]);
            }

            row.appendChild(swatch);
            row.appendChild(label);
            legendItems.appendChild(row);
        }
    }

    // -----------------------------------------------------------------------
    // Summary stats
    // -----------------------------------------------------------------------
    function updateStats() {
        let totalAwards  = 0;
        let totalFunding = 0;
        let townCount    = 0;

        Object.values(municipalityData).forEach(d => {
            townCount++;
            totalAwards  += d.award_count || 0;
            totalFunding += d.total_funding || 0;
        });

        statTowns.textContent   = formatNumber(townCount);
        statAwards.textContent  = formatNumber(totalAwards);
        statFunding.textContent = formatCompact(totalFunding);
    }

    // -----------------------------------------------------------------------
    // Interactions — hover
    // -----------------------------------------------------------------------
    let hoveredId = null;

    function onMouseMove(e) {
        if (e.features.length === 0) return;

        // Clear previous hover
        if (hoveredId !== null) {
            map.setFeatureState({ source: 'ct-towns', id: hoveredId }, { hover: false });
        }

        hoveredId = e.features[0].id;
        map.setFeatureState({ source: 'ct-towns', id: hoveredId }, { hover: true });

        // Show tooltip
        const name = e.features[0].properties.Municipality;
        hoverTooltip.textContent = name;
        hoverTooltip.style.display = 'block';
        hoverTooltip.style.left = (e.point.x + 12) + 'px';
        hoverTooltip.style.top  = (e.point.y - 12) + 'px';

        map.getCanvas().style.cursor = 'pointer';
    }

    function onMouseLeave() {
        if (hoveredId !== null) {
            map.setFeatureState({ source: 'ct-towns', id: hoveredId }, { hover: false });
        }
        hoveredId = null;
        hoverTooltip.style.display = 'none';
        map.getCanvas().style.cursor = '';
    }

    // -----------------------------------------------------------------------
    // Interactions — click popup
    // -----------------------------------------------------------------------
    function onClick(e) {
        if (e.features.length === 0) return;

        const props   = e.features[0].properties;
        const name    = props.Municipality;
        const data    = municipalityData[name] || {};
        const awards  = data.award_count   || 0;
        const funding = data.total_funding || 0;
        const region  = props.PlanningRegion || 'N/A';
        const county  = props.County || 'N/A';

        const tearSheetUrl = '/auth/municipality/'
            + encodeURIComponent(name) + '/'
            + '?county=' + encodeURIComponent(county)
            + '&region=' + encodeURIComponent(region);

        const html = `
            <div class="popup-title">${name}</div>
            <div class="popup-row">
                <span class="popup-label">Awards:</span>
                <span class="popup-value">${formatNumber(awards)}</span>
            </div>
            <div class="popup-row">
                <span class="popup-label">Funding:</span>
                <span class="popup-value">${formatCurrency(funding)}</span>
            </div>
            <div class="popup-row">
                <span class="popup-label">Region:</span>
                <span class="popup-value">${region}</span>
            </div>
            <div class="popup-row">
                <span class="popup-label">County:</span>
                <span class="popup-value">${county}</span>
            </div>
            <div style="margin-top: 8px; text-align: center;">
                <a href="${tearSheetUrl}"
                   class="btn btn-sm btn-primary"
                   style="font-size: 0.8rem;">
                    <i class="bi bi-file-earmark-text me-1"></i>View Details
                </a>
            </div>
        `;

        new mapboxgl.Popup({ maxWidth: '260px' })
            .setLngLat(e.lngLat)
            .setHTML(html)
            .addTo(map);
    }

    // -----------------------------------------------------------------------
    // Town selector — fly to
    // -----------------------------------------------------------------------
    function flyToTown(name) {
        if (!name || !geojsonData) return;

        const feature = geojsonData.features.find(
            f => f.properties.Municipality === name,
        );
        if (!feature) return;

        const bbox = turf.bbox(feature);
        map.fitBounds(
            [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
            { padding: 80, maxZoom: 12 },
        );
    }

    // -----------------------------------------------------------------------
    // Filter & metric handlers
    // -----------------------------------------------------------------------

    /** Reload data from API with current filters and re-render. */
    async function refreshMap() {
        await loadMapData();
        renderChoropleth();
    }

    metricSelect.addEventListener('change', () => {
        currentMetric = metricSelect.value;
        renderChoropleth();
    });

    agencySelect.addEventListener('change', refreshMap);
    programSelect.addEventListener('change', refreshMap);

    townSelect.addEventListener('change', () => {
        flyToTown(townSelect.value);
    });

    resetBtn.addEventListener('click', () => {
        agencySelect.value  = '';
        programSelect.value = '';
        townSelect.value    = '';
        metricSelect.value  = 'total_funding';
        currentMetric       = 'total_funding';

        map.fitBounds(CT_BOUNDS, { padding: 20 });

        refreshMap();
    });

    // -----------------------------------------------------------------------
    // Boot sequence
    // -----------------------------------------------------------------------
    map.on('load', async () => {
        await loadGeoJSON();
        await loadMapData();
        renderChoropleth();

        // Attach interactions
        map.on('mousemove', 'ct-towns-fill', onMouseMove);
        map.on('mouseleave', 'ct-towns-fill', onMouseLeave);
        map.on('click', 'ct-towns-fill', onClick);
    });
})();
