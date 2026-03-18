/**
 * Beacon Analytics Dashboard Charts
 *
 * Renders four interactive Chart.js charts using data embedded in the page
 * via Django's json_script template filter.
 *
 * Charts:
 *   1. Application Status Distribution (doughnut)
 *   2. Funding by Agency (horizontal bar)
 *   3. Award Trends (line / area)
 *   4. Budget Utilization (grouped bar)
 *
 * CT Brand palette:
 *   Primary  #00457C   Secondary #A8B400   Accent #00857C
 */
(function () {
  'use strict';

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  /**
   * Format a number as US-dollar currency.
   */
  function fmtCurrency(value) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  }

  /**
   * Map an application status label to a brand-appropriate colour.
   */
  function statusColor(label) {
    var map = {
      'Draft':              '#6c757d',
      'Submitted':          '#0d6efd',
      'Under Review':       '#F27124',
      'Revision Requested': '#fd7e14',
      'Approved':           '#198754',
      'Denied':             '#dc3545',
      'Withdrawn':          '#343a40',
    };
    return map[label] || '#adb5bd';
  }

  // ------------------------------------------------------------------
  // Shared defaults
  // ------------------------------------------------------------------

  Chart.defaults.font.family = "'Poppins', 'Segoe UI', sans-serif";
  Chart.defaults.font.size = 13;
  Chart.defaults.color = '#495057';
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.plugins.tooltip.padding = 10;

  // ------------------------------------------------------------------
  // Read embedded data
  // ------------------------------------------------------------------

  var dataEl = document.getElementById('chart-data');
  if (!dataEl) return;

  var data;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (e) {
    console.error('Failed to parse chart data:', e);
    return;
  }

  // ------------------------------------------------------------------
  // 1. Application Status Distribution  (Doughnut)
  // ------------------------------------------------------------------

  var statusCtx = document.getElementById('chartStatusDistribution');
  if (statusCtx && data.status && Object.keys(data.status).length) {
    var statusLabels = Object.keys(data.status);
    var statusValues = Object.values(data.status);
    var statusColors = statusLabels.map(statusColor);

    new Chart(statusCtx, {
      type: 'doughnut',
      data: {
        labels: statusLabels,
        datasets: [{
          data: statusValues,
          backgroundColor: statusColors,
          borderWidth: 2,
          borderColor: '#ffffff',
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '55%',
        plugins: {
          legend: {
            position: 'right',
            labels: {
              padding: 16,
              usePointStyle: true,
              pointStyleWidth: 12,
            },
          },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var total = ctx.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                var pct = total ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                return ' ' + ctx.label + ': ' + ctx.parsed + ' (' + pct + '%)';
              },
            },
          },
        },
      },
    });
  }

  // ------------------------------------------------------------------
  // 2. Funding by Agency  (Horizontal Bar)
  // ------------------------------------------------------------------

  var agencyCtx = document.getElementById('chartFundingByAgency');
  if (agencyCtx && data.agency && Object.keys(data.agency).length) {
    var agencyLabels = Object.keys(data.agency);
    var agencyValues = Object.values(data.agency);

    new Chart(agencyCtx, {
      type: 'bar',
      data: {
        labels: agencyLabels,
        datasets: [{
          label: 'Total Funding',
          data: agencyValues,
          backgroundColor: '#00457C',
          borderColor: '#003460',
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.7,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ' ' + fmtCurrency(ctx.parsed.x);
              },
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return fmtCurrency(value);
              },
            },
            grid: { color: 'rgba(0,0,0,0.06)' },
          },
          y: {
            grid: { display: false },
          },
        },
      },
    });
  }

  // ------------------------------------------------------------------
  // 3. Award Trends  (Line / Area)
  // ------------------------------------------------------------------

  var monthlyCtx = document.getElementById('chartAwardTrends');
  if (monthlyCtx && data.monthly_awards && Object.keys(data.monthly_awards).length) {
    var monthLabels = Object.keys(data.monthly_awards);
    var monthValues = Object.values(data.monthly_awards);

    new Chart(monthlyCtx, {
      type: 'line',
      data: {
        labels: monthLabels,
        datasets: [{
          label: 'Awards',
          data: monthValues,
          borderColor: '#00857C',
          backgroundColor: 'rgba(0, 133, 124, 0.12)',
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#00857C',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ' ' + ctx.parsed.y + (ctx.parsed.y === 1 ? ' award' : ' awards');
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(0,0,0,0.06)' },
          },
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0,
            },
            grid: { color: 'rgba(0,0,0,0.06)' },
          },
        },
      },
    });
  }

  // ------------------------------------------------------------------
  // 4. Budget Utilization  (Grouped Bar)
  // ------------------------------------------------------------------

  var budgetCtx = document.getElementById('chartBudgetUtilization');
  if (budgetCtx && data.budget && Object.keys(data.budget).length) {
    var budgetLabels = Object.keys(data.budget);
    var awardedValues = budgetLabels.map(function (k) { return data.budget[k].awarded; });
    var disbursedValues = budgetLabels.map(function (k) { return data.budget[k].disbursed; });

    new Chart(budgetCtx, {
      type: 'bar',
      data: {
        labels: budgetLabels,
        datasets: [
          {
            label: 'Awarded',
            data: awardedValues,
            backgroundColor: '#00457C',
            borderColor: '#003460',
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: 'Disbursed',
            data: disbursedValues,
            backgroundColor: '#A8B400',
            borderColor: '#8a9500',
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { usePointStyle: true, pointStyleWidth: 12, padding: 16 },
          },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ' ' + ctx.dataset.label + ': ' + fmtCurrency(ctx.parsed.y);
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              maxRotation: 45,
              minRotation: 20,
            },
          },
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return fmtCurrency(value);
              },
            },
            grid: { color: 'rgba(0,0,0,0.06)' },
          },
        },
      },
    });
  }

})();
