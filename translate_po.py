#!/usr/bin/env python3
"""
Translate Harbor .po file from English to Spanish.
Comprehensive dictionary-based translation for CT grants management system.
"""
import re

# ============================================================================
# COMPREHENSIVE ENGLISH → SPANISH DICTIONARY
# ============================================================================
TRANSLATIONS = {
    # --- Status Labels ---
    "Draft": "Borrador",
    "Submitted": "Enviado",
    "Under Review": "En revisión",
    "Revision Requested": "Revisión solicitada",
    "Approved": "Aprobado",
    "Denied": "Denegado",
    "Withdrawn": "Retirado",
    "Pending Approval": "Aprobación pendiente",
    "Executed": "Ejecutado",
    "Active": "Activo",
    "On Hold": "En espera",
    "Completed": "Completado",
    "Terminated": "Terminado",
    "Cancelled": "Cancelado",
    "Sent": "Enviado",
    "Delivered": "Entregado",
    "Signed": "Firmado",
    "Declined": "Rechazado",
    "Voided": "Anulado",
    "Not Started": "No iniciado",
    "In Progress": "En progreso",
    "Pending Review": "Revisión pendiente",
    "Pending": "Pendiente",
    "Reopened": "Reabierto",
    "Assigned": "Asignado",
    "In Progress": "En progreso",
    "Recused": "Recusado",
    "Paid": "Pagado",
    "Returned": "Devuelto",
    "Processed": "Procesado",
    "Confirmed": "Confirmado",
    "Posted": "Publicado",
    "Accepting Applications": "Aceptando solicitudes",
    "Under Review": "En revisión",
    "Awards Pending": "Adjudicaciones pendientes",
    "Closed": "Cerrado",

    # --- Navigation / UI ---
    "Dashboard": "Panel de control",
    "Home": "Inicio",
    "Login": "Iniciar sesión",
    "Logout": "Cerrar sesión",
    "Log In": "Iniciar sesión",
    "Log Out": "Cerrar sesión",
    "Register": "Registrarse",
    "Profile": "Perfil",
    "Search": "Buscar",
    "Filter": "Filtrar",
    "Submit": "Enviar",
    "Save": "Guardar",
    "Save Draft": "Guardar borrador",
    "Cancel": "Cancelar",
    "Delete": "Eliminar",
    "Edit": "Editar",
    "View": "Ver",
    "Back": "Volver",
    "Next": "Siguiente",
    "Previous": "Anterior",
    "Close": "Cerrar",
    "Download": "Descargar",
    "Upload": "Subir",
    "Export": "Exportar",
    "Export CSV": "Exportar CSV",
    "Print": "Imprimir",
    "Actions": "Acciones",
    "Details": "Detalles",
    "Status": "Estado",
    "Title": "Título",
    "Description": "Descripción",
    "Date": "Fecha",
    "Type": "Tipo",
    "Name": "Nombre",
    "Email": "Correo electrónico",
    "Phone": "Teléfono",
    "Address": "Dirección",
    "Notes": "Notas",
    "Comments": "Comentarios",
    "Created": "Creado",
    "Updated": "Actualizado",
    "Loading": "Cargando",
    "None": "Ninguno",
    "Yes": "Sí",
    "No": "No",
    "All": "Todos",
    "Other": "Otro",
    "Total": "Total",
    "Amount": "Monto",
    "OR": "O",
    "to": "a",
    "of": "de",
    "d": "d",
    "and": "y",
    "or": "o",
    "N/A": "N/A",
    "Username": "Nombre de usuario",
    "Password": "Contraseña",
    "English": "Inglés",
    "Spanish": "Español",

    # --- Grant Terms ---
    "Grant": "Subvención",
    "Grants": "Subvenciones",
    "Grant Program": "Programa de subvención",
    "Grant Programs": "Programas de subvención",
    "Application": "Solicitud",
    "Applications": "Solicitudes",
    "Award": "Adjudicación",
    "Awards": "Adjudicaciones",
    "Budget": "Presupuesto",
    "Budgets": "Presupuestos",
    "Report": "Informe",
    "Reports": "Informes",
    "Review": "Revisión",
    "Reviews": "Revisiones",
    "Closeout": "Cierre",
    "Closeouts": "Cierres",
    "Amendment": "Enmienda",
    "Amendments": "Enmiendas",
    "Drawdown Request": "Solicitud de desembolso",
    "Drawdown Requests": "Solicitudes de desembolso",
    "Drawdown": "Desembolso",
    "Transaction": "Transacción",
    "Transactions": "Transacciones",
    "Funding": "Financiamiento",
    "Organization": "Organización",
    "Organizations": "Organizaciones",
    "Agency": "Agencia",
    "Agencies": "Agencias",
    "Notification": "Notificación",
    "Notifications": "Notificaciones",
    "Audit Log": "Registro de auditoría",
    "Audit Logs": "Registros de auditoría",

    # --- Organization Types ---
    "Organization Type": "Tipo de organización",
    "Municipality": "Municipio",
    "Nonprofit": "Sin fines de lucro",
    "Business": "Empresa",
    "Individual": "Individual",
    "Educational Institution": "Institución educativa",
    "Tribal Nation": "Nación tribal",

    # --- User Roles ---
    "System Administrator": "Administrador del sistema",
    "Agency Administrator": "Administrador de agencia",
    "Program Officer": "Oficial de programa",
    "Fiscal Officer": "Oficial fiscal",
    "Reviewer": "Revisor",
    "Applicant": "Solicitante",
    "Auditor": "Auditor",

    # --- Audit Actions ---
    "Create": "Crear",
    "Update": "Actualizar",
    "Status Change": "Cambio de estado",
    "Approve": "Aprobar",
    "Reject": "Rechazar",

    # --- Notification Priority ---
    "Low": "Bajo",
    "Medium": "Medio",
    "High": "Alto",
    "Urgent": "Urgente",

    # --- Application Documents ---
    "Project Narrative": "Narrativa del proyecto",
    "Budget Justification": "Justificación del presupuesto",
    "Letters of Support": "Cartas de apoyo",
    "Resumes / CVs": "Currículos / CVs",
    "Organizational Chart": "Organigrama",
    "Audit Report": "Informe de auditoría",
    "Tax-Exempt Determination Letter": "Carta de determinación de exención fiscal",
    "Application Document": "Documento de solicitud",
    "Application Documents": "Documentos de solicitud",

    # --- Application Compliance ---
    "SAM Registration Active": "Registro SAM activo",
    "Tax-Exempt Status Verified": "Estado de exención fiscal verificado",
    "Audit Clearance": "Autorización de auditoría",
    "Debarment / Suspension Check": "Verificación de inhabilitación / suspensión",
    "Budget Review Complete": "Revisión de presupuesto completa",
    "Narrative Review Complete": "Revisión narrativa completa",
    "Insurance Verification": "Verificación de seguro",
    "Match Funds Verified": "Fondos de contrapartida verificados",
    "Conflict of Interest Check": "Verificación de conflicto de intereses",
    "Eligibility Confirmed": "Elegibilidad confirmada",
    "Application Compliance Item": "Elemento de cumplimiento de solicitud",
    "Application Compliance Items": "Elementos de cumplimiento de solicitud",

    # --- Staff Documents ---
    "Verification Document": "Documento de verificación",
    "Background Check": "Verificación de antecedentes",
    "Due Diligence Memo": "Memorando de diligencia debida",
    "Reference Check": "Verificación de referencias",
    "Site Visit Report": "Informe de visita al sitio",
    "Legal Review": "Revisión legal",
    "Financial Review": "Revisión financiera",
    "Staff Document": "Documento del personal",
    "Staff Documents": "Documentos del personal",
    "Application Comment": "Comentario de solicitud",
    "Application Comments": "Comentarios de solicitud",
    "Application Section": "Sección de solicitud",
    "Application Sections": "Secciones de solicitud",
    "Application Status History": "Historial de estado de solicitud",
    "Application Status Histories": "Historiales de estado de solicitud",

    # --- Funding Source ---
    "Federal": "Federal",
    "State": "Estatal",
    "Private": "Privado",
    "Mixed": "Mixto",
    "Funding Source": "Fuente de financiamiento",
    "Funding Sources": "Fuentes de financiamiento",

    # --- Grant Program Types ---
    "Competitive": "Competitivo",
    "Non-Competitive": "No competitivo",
    "Formula": "Fórmula",
    "Continuation": "Continuación",
    "Grant Program Document": "Documento de programa de subvención",
    "Grant Program Documents": "Documentos de programa de subvención",

    # --- Grant Program Document Types ---
    "Notice of Funding Availability": "Aviso de disponibilidad de fondos",
    "Program Guidelines": "Directrices del programa",
    "Budget Template": "Plantilla de presupuesto",
    "Application Form": "Formulario de solicitud",
    "FAQ": "Preguntas frecuentes",

    # --- Award Documents ---
    "Agreement": "Acuerdo",
    "Correspondence": "Correspondencia",
    "Award Document": "Documento de adjudicación",
    "Award Documents": "Documentos de adjudicación",
    "Award Amendment": "Enmienda de adjudicación",
    "Award Amendments": "Enmiendas de adjudicación",

    # --- Amendment Types ---
    "Budget Modification": "Modificación de presupuesto",
    "Time Extension": "Extensión de tiempo",
    "Scope Change": "Cambio de alcance",
    "Personnel Change": "Cambio de personal",

    # --- Sub-Recipient ---
    "Sub-Recipient": "Sub-receptor",
    "Sub-Recipients": "Sub-receptores",
    "Suspended": "Suspendido",
    "Inactive": "Inactivo",

    # --- Performance Metrics ---
    "Output": "Resultado",
    "Outcome": "Impacto",
    "Efficiency": "Eficiencia",
    "Performance Metric": "Métrica de rendimiento",
    "Performance Metrics": "Métricas de rendimiento",

    # --- Financial ---
    "Budget Line Item": "Partida presupuestaria",
    "Budget Line Items": "Partidas presupuestarias",
    "Personnel": "Personal",
    "Fringe Benefits": "Beneficios complementarios",
    "Travel": "Viajes",
    "Equipment": "Equipos",
    "Supplies": "Suministros",
    "Contractual": "Contractual",
    "Construction": "Construcción",
    "Indirect Costs": "Costos indirectos",
    "Obligation": "Obligación",
    "Payment": "Pago",
    "Refund": "Reembolso",
    "Adjustment": "Ajuste",
    "State ERP Account String": "Cadena de cuenta del ERP estatal",
    "State ERP Account Strings": "Cadenas de cuenta del ERP estatal",
    "State ERP Reference": "Referencia del ERP estatal",
    "Fund": "Fondo",
    "Department": "Departamento",
    "SID": "SID",
    "Program": "Programa",
    "Account": "Cuenta",
    "Chartfield 1": "Chartfield 1",
    "Chartfield 2": "Chartfield 2",
    "Budget Ref Year": "Año de referencia presupuestaria",
    "Project": "Proyecto",

    # --- Reporting ---
    "Progress": "Progreso",
    "Fiscal": "Fiscal",
    "Programmatic": "Programático",
    "Final Progress": "Progreso final",
    "Final Fiscal": "Fiscal final",
    "SF-425 Federal Financial Report": "Informe financiero federal SF-425",
    "Custom": "Personalizado",
    "Monthly": "Mensual",
    "Quarterly": "Trimestral",
    "Semi-Annual": "Semestral",
    "Annual": "Anual",
    "One Time": "Una vez",
    "As Needed": "Según sea necesario",
    "Report Template": "Plantilla de informe",
    "Report Templates": "Plantillas de informe",
    "Report Document": "Documento de informe",
    "Report Documents": "Documentos de informe",
    "SF-425 Report": "Informe SF-425",
    "SF-425 Reports": "Informes SF-425",

    # --- Closeout ---
    "Closeout Checklist Item": "Elemento de lista de verificación de cierre",
    "Closeout Checklist Items": "Elementos de lista de verificación de cierre",
    "Closeout Document": "Documento de cierre",
    "Closeout Documents": "Documentos de cierre",
    "Fund Return": "Devolución de fondos",
    "Fund Returns": "Devoluciones de fondos",
    "Final Progress Report": "Informe final de progreso",
    "Final Fiscal Report": "Informe fiscal final",
    "Inventory Report": "Informe de inventario",
    "Refund Documentation": "Documentación de reembolso",

    # --- Reviews ---
    "Review Rubric": "Rúbrica de revisión",
    "Review Rubrics": "Rúbricas de revisión",
    "Rubric Criterion": "Criterio de rúbrica",
    "Rubric Criteria": "Criterios de rúbrica",
    "Review Assignment": "Asignación de revisión",
    "Review Assignments": "Asignaciones de revisión",
    "Review Score": "Puntuación de revisión",
    "Review Scores": "Puntuaciones de revisión",
    "Review Summary": "Resumen de revisión",
    "Review Summaries": "Resúmenes de revisión",
    "Do Not Fund": "No financiar",
    "Fund with Conditions": "Financiar con condiciones",
    "Needs Discussion": "Necesita discusión",

    # --- Archived Records ---
    "Archived Record": "Registro archivado",
    "Archived Records": "Registros archivados",
    "Standard (7 years)": "Estándar (7 años)",
    "Extended (10 years)": "Extendido (10 años)",
    "Permanent": "Permanente",
    "Federal Requirement (3 years post-closeout)": "Requisito federal (3 años después del cierre)",

    # --- DocuSign / Signatures ---
    "Signature Request": "Solicitud de firma",
    "Signature Requests": "Solicitudes de firma",
    "Request Signature": "Solicitar firma",
    "Signer Name": "Nombre del firmante",
    "Signer Email": "Correo electrónico del firmante",
    "CC Email (optional)": "Correo CC (opcional)",
    "Send for Signature": "Enviar para firma",
    "Signature Status": "Estado de firma",

    # --- Map View ---
    "Map View": "Vista de mapa",
    "Total Funding": "Financiamiento total",
    "Award Count": "Cantidad de adjudicaciones",
    "Planning Region": "Región de planificación",
    "County": "Condado",

    # --- Form Labels ---
    "First Name": "Nombre",
    "Last Name": "Apellido",
    "Email Address": "Correo electrónico",
    "Confirm Password": "Confirmar contraseña",
    "Create Account": "Crear cuenta",
    "Create Your Account": "Cree su cuenta",
    "Sign in with Microsoft": "Iniciar sesión con Microsoft",
    "Category": "Categoría",
    "User": "Usuario",
    "Users": "Usuarios",

    # --- Admin ---
    "Harbor Administration": "Administración de Harbor",
    "Harbor Admin": "Admin de Harbor",
    "Grants Management System": "Sistema de gestión de subvenciones",

    # --- Common Help Text ---
    "Amount of funding requested": "Monto de financiamiento solicitado",
    "Proposed matching contribution amount": "Monto propuesto de contribución de contrapartida",
    "Description of matching funds or in-kind contributions": "Descripción de fondos de contrapartida o contribuciones en especie",
    "Flexible form data stored as JSON": "Datos flexibles del formulario almacenados como JSON",
    "If True, this comment is visible only to staff reviewers": "Si es verdadero, este comentario es visible solo para los revisores del personal",
    "Human-readable description of the compliance requirement": "Descripción legible del requisito de cumplimiento",
    "Staff notes about this compliance item": "Notas del personal sobre este elemento de cumplimiento",
    "Whether this item must be verified before approval": "Si este elemento debe ser verificado antes de la aprobación",
    "Catalog of Federal Domestic Assistance number (federal sources only)": "Número del catálogo de asistencia federal doméstica (solo fuentes federales)",
    "Originating federal agency, if applicable": "Agencia federal de origen, si aplica",
    "Description of who may apply": "Descripción de quién puede solicitar",
    "Total funding available for this program": "Financiamiento total disponible para este programa",
    "Minimum award amount": "Monto mínimo de adjudicación",
    "Maximum award amount": "Monto máximo de adjudicación",
    "Whether a matching contribution is required": "Si se requiere una contribución de contrapartida",
    "Required match as a percentage (e.g. 25.00 for 25%)": "Contrapartida requerida como porcentaje (ej. 25.00 para 25%)",
    "e.g. 2025-2026": "ej. 2025-2026",
    "Whether awards span multiple fiscal years": "Si las adjudicaciones abarcan múltiples años fiscales",
    "Grant period duration in months": "Duración del período de subvención en meses",
    "JSON configuration defining custom application form sections and fields per program": "Configuración JSON que define secciones y campos personalizados del formulario de solicitud por programa",
    "e.g. people served, jobs created": "ej. personas atendidas, empleos creados",
    "Can this agency receive grants from other agencies?": "¿Puede esta agencia recibir subvenciones de otras agencias?",
    "Can this agency award grants?": "¿Puede esta agencia otorgar subvenciones?",
    "Designates whether this user is a state government employee.": "Indica si este usuario es un empleado del gobierno estatal.",
    "State ERP Department Code": "Código de departamento del ERP estatal",
    "Fund Code": "Código de fondo",
    "Program Code": "Código de programa",
    "DUNS Number": "Número DUNS",
    "UEI Number": "Número UEI",
    "EIN": "EIN",
    "SAM Registered": "Registrado en SAM",
    "SAM Expiration Date": "Fecha de vencimiento SAM",
    "When the original record was created": "Cuando se creó el registro original",
    "When this archived record can be permanently deleted": "Cuando este registro archivado puede ser eliminado permanentemente",
    "Preserved metadata from the archived record": "Metadatos preservados del registro archivado",
    "Whether the original record has been purged from the system": "Si el registro original ha sido purgado del sistema",
    "Leave blank for statewide templates.": "Dejar en blanco para plantillas estatales.",
    "Defines the report structure and fields.": "Define la estructura y campos del informe.",
    "Stores the actual report data.": "Almacena los datos reales del informe.",
    "Stores all SF-425 fields.": "Almacena todos los campos SF-425.",
    "Reference ID from the state enterprise financial system.": "ID de referencia del sistema financiero empresarial estatal.",

    # --- Dashboard / Analytics ---
    "Analytics Dashboard": "Panel de análisis",
    "Analytics": "Análisis",
    "Overview": "Resumen",
    "Recent Activity": "Actividad reciente",
    "Quick Stats": "Estadísticas rápidas",
    "Total Programs": "Total de programas",
    "Active Programs": "Programas activos",
    "Active Awards": "Adjudicaciones activas",
    "Total Awards": "Total de adjudicaciones",
    "Pending Applications": "Solicitudes pendientes",
    "Total Applications": "Total de solicitudes",
    "Approval Rate": "Tasa de aprobación",
    "Total Disbursed": "Total desembolsado",
    "Pending Drawdowns": "Desembolsos pendientes",
    "Overdue Reports": "Informes vencidos",
    "Financial Overview": "Resumen financiero",
    "Funding Awarded": "Financiamiento adjudicado",
    "Funding Disbursed": "Financiamiento desembolsado",
    "Application Status Distribution": "Distribución de estado de solicitudes",
    "Agency Breakdown": "Desglose por agencia",
    "Recent Applications": "Solicitudes recientes",
    "Recent Awards": "Adjudicaciones recientes",
    "Award Trends": "Tendencias de adjudicaciones",
    "Budget Utilization": "Utilización del presupuesto",
    "Funding by Agency": "Financiamiento por agencia",

    # --- Calendar ---
    "Calendar": "Calendario",
    "Upcoming Deadlines": "Fechas límite próximas",
    "Today": "Hoy",
    "This Week": "Esta semana",
    "This Month": "Este mes",

    # --- Portal ---
    "Welcome to Harbor": "Bienvenido a Harbor",
    "Funding Opportunities": "Oportunidades de financiamiento",
    "Opportunities": "Oportunidades",
    "About": "Acerca de",
    "Help": "Ayuda",
    "Contact": "Contacto",
    "Apply Now": "Solicitar ahora",
    "Learn More": "Más información",
    "View Details": "Ver detalles",
    "Start Application": "Iniciar solicitud",
    "Continue Application": "Continuar solicitud",
    "View Application": "Ver solicitud",
    "My Applications": "Mis solicitudes",
    "My Awards": "Mis adjudicaciones",

    # --- Common Template Strings ---
    "Award Number": "Número de adjudicación",
    "Award Amount": "Monto de adjudicación",
    "Award Date": "Fecha de adjudicación",
    "Start Date": "Fecha de inicio",
    "End Date": "Fecha de finalización",
    "Due Date": "Fecha de vencimiento",
    "Submitted Date": "Fecha de envío",
    "Created Date": "Fecha de creación",
    "Last Updated": "Última actualización",
    "Awarded": "Adjudicado",
    "Disbursed": "Desembolsado",
    "Remaining": "Restante",
    "Balance": "Saldo",
    "Expended": "Gastado",
    "No results found": "No se encontraron resultados",
    "No data available": "No hay datos disponibles",
    "Are you sure?": "¿Está seguro?",
    "Confirm": "Confirmar",
    "Select": "Seleccionar",
    "Choose": "Elegir",
    "Required": "Requerido",
    "Optional": "Opcional",
    "Showing": "Mostrando",
    "Page": "Página",
    "Items per page": "Elementos por página",
    "Sort by": "Ordenar por",
    "Ascending": "Ascendente",
    "Descending": "Descendente",

    # --- Application Detail ---
    "Application Details": "Detalles de la solicitud",
    "Application Information": "Información de la solicitud",
    "Project Title": "Título del proyecto",
    "Project Description": "Descripción del proyecto",
    "Requested Amount": "Monto solicitado",
    "Match Amount": "Monto de contrapartida",
    "Compliance Status": "Estado de cumplimiento",
    "Documents": "Documentos",
    "Timeline": "Cronología",
    "History": "Historial",

    # --- Award Detail ---
    "Award Details": "Detalles de la adjudicación",
    "Award Information": "Información de la adjudicación",
    "Terms and Conditions": "Términos y condiciones",
    "Special Conditions": "Condiciones especiales",
    "Performance": "Rendimiento",
    "Sub-Recipients": "Sub-receptores",

    # --- Financial Detail ---
    "Budget Details": "Detalles del presupuesto",
    "Budget Summary": "Resumen del presupuesto",
    "Line Items": "Partidas",
    "Drawdown Details": "Detalles de desembolso",
    "Transaction History": "Historial de transacciones",
    "Request Amount": "Monto solicitado",
    "Approved Amount": "Monto aprobado",

    # --- Report Detail ---
    "Report Details": "Detalles del informe",
    "Report Content": "Contenido del informe",
    "Reporting Period": "Período de informe",
    "Report Type": "Tipo de informe",
    "Narrative Summary": "Resumen narrativo",
    "Key Accomplishments": "Logros clave",
    "Challenges": "Desafíos",
    "Goals for Next Period": "Metas para el próximo período",
    "Expenditure Summary": "Resumen de gastos",
    "Fiscal Narrative": "Narrativa fiscal",
    "Reviewer Comments": "Comentarios del revisor",
    "Attached Documents": "Documentos adjuntos",

    # --- Review ---
    "Review Dashboard": "Panel de revisión",
    "Review Application": "Revisar solicitud",
    "Assign Reviewer": "Asignar revisor",
    "Score": "Puntuación",
    "Weight": "Peso",
    "Criterion": "Criterio",
    "Max Score": "Puntuación máxima",
    "Average Score": "Puntuación promedio",
    "Total Score": "Puntuación total",
    "Total Score:": "Puntuación total:",
    "Recommendation": "Recomendación",
    "Risk Assessment": "Evaluación de riesgo",
    "Risk Assessment Details": "Detalles de evaluación de riesgo",
    "Low Risk": "Riesgo bajo",
    "Medium Risk": "Riesgo medio",
    "High Risk": "Riesgo alto",
    "Not Assessed": "No evaluado",
    "Min": "Mín",
    "Max": "Máx",
    "Weighted Avg": "Promedio ponderado",
    "Overall Totals": "Totales generales",
    "Scoring Criteria": "Criterios de puntuación",

    # --- Closeout ---
    "Closeout Details": "Detalles del cierre",
    "Closeout Checklist": "Lista de verificación de cierre",
    "Fund Return Form": "Formulario de devolución de fondos",

    # --- Common Messages ---
    "has been created successfully.": "ha sido creado exitosamente.",
    "has been updated successfully.": "ha sido actualizado exitosamente.",
    "has been submitted successfully.": "ha sido enviado exitosamente.",
    "has been approved successfully.": "ha sido aprobado exitosamente.",
    "has been denied.": "ha sido denegado.",
    "has been deleted.": "ha sido eliminado.",
    "successfully": "exitosamente",
    "Error": "Error",
    "Warning": "Advertencia",
    "Information": "Información",
    "Success": "Éxito",

    # --- Login/Register ---
    "State employees: use your DOK.gov account": "Empleados estatales: utilicen su cuenta DOK.gov",
    "Contact your system administrator to reset your password": "Contacte a su administrador del sistema para restablecer su contraseña",
    "Forgot password? Contact your administrator.": "¿Olvidó su contraseña? Contacte a su administrador.",
    "Don't have an account?": "¿No tiene una cuenta?",
    "Already have an account?": "¿Ya tiene una cuenta?",
    "Register for the State Grants Management Solution": "Regístrese en la Solución de gestión de subvenciones estatal",

    # --- SF-425 ---
    "SF-425": "SF-425",
    "FEDERAL FINANCIAL REPORT": "INFORME FINANCIERO FEDERAL",
    "(Follow instructions on the back)": "(Siga las instrucciones en el reverso)",
    "Federal Cash": "Efectivo federal",
    "Cash Receipts": "Recibos de efectivo",
    "Cash Disbursements": "Desembolsos de efectivo",
    "Federal Share": "Participación federal",
    "Recipient Share": "Participación del receptor",
    "Program Income": "Ingreso del programa",
    "Indirect Expense": "Gasto indirecto",
    "Certification": "Certificación",
    "Remarks": "Observaciones",

    # --- User Management ---
    "User Management": "Gestión de usuarios",
    "Edit User Role": "Editar rol de usuario",
    "Role & Permissions": "Rol y permisos",
    "User Information": "Información del usuario",
    "Role Descriptions": "Descripciones de roles",
    "Current Role:": "Rol actual:",
    "Username:": "Nombre de usuario:",
    "State Employee": "Empleado estatal",
    "State Employee:": "Empleado estatal:",
    "Account Active": "Cuenta activa",
    "All Roles": "Todos los roles",
    "Back to Users": "Volver a usuarios",
    "users": "usuarios",
    "No users found.": "No se encontraron usuarios.",
    "Search by name, username, or email...": "Buscar por nombre, usuario o correo...",
    "Change Password": "Cambiar contraseña",
    "Full system access. Manages all agencies, programs, users, and settings.": "Acceso completo al sistema. Gestiona todas las agencias, programas, usuarios y configuraciones.",
    "Manages programs and awards for their assigned agency.": "Gestiona programas y adjudicaciones para su agencia asignada.",
    "Manages specific grant programs and reviews applications.": "Gestiona programas de subvención específicos y revisa solicitudes.",
    "Manages financial transactions, drawdowns, and budget tracking.": "Gestiona transacciones financieras, desembolsos y seguimiento presupuestario.",
    "Reviews and scores grant applications.": "Revisa y califica solicitudes de subvención.",
    "External grant applicant. Can submit applications and view awards.": "Solicitante externo de subvenciones. Puede enviar solicitudes y ver adjudicaciones.",
    "Read-only access to review grant records and financial data.": "Acceso de solo lectura para revisar registros de subvenciones y datos financieros.",
    "To add a new grant administrator, ask the user to register at the public registration page, then change their role here. State employees should use the Microsoft SSO login.": "Para agregar un nuevo administrador de subvenciones, pida al usuario que se registre en la página de registro público y luego cambie su rol aquí. Los empleados estatales deben usar el inicio de sesión SSO de Microsoft.",
    "Clear": "Limpiar",

    # --- Misc ---
    "State Grants Management Solution": "Solución de gestión de subvenciones estatal",
    "State of DOK": "Estado de DOK",
    "Harbor": "Harbor",
    "No Opportunities Found": "No se encontraron oportunidades",
    "Deadline passed": "Fecha límite vencida",
    "Not Accepting Applications": "No se aceptan solicitudes",
    "Eligibility Criteria": "Criterios de elegibilidad",
    "Key Details": "Detalles clave",
    "Duration": "Duración",
    "Match Requirement": "Requisito de contrapartida",
    "Contact Information": "Información de contacto",
    "Quick Info": "Información rápida",
    "Ready to Submit?": "¿Listo para enviar?",
    "Edit Report": "Editar informe",
    "Create Report": "Crear informe",
    "Clear filters": "Limpiar filtros",
    "Apply Filters": "Aplicar filtros",
    "All Types": "Todos los tipos",
    "All Statuses": "Todos los estados",
    "All Agencies": "Todas las agencias",
    "Program Status": "Estado del programa",
    "Grant Type": "Tipo de subvención",
    "My Application": "Mi solicitud",
    "View Full Application": "Ver solicitud completa",
    "Submit Review": "Enviar revisión",
    "Back to Application": "Volver a la solicitud",
    "Back to Reports": "Volver a informes",
    "Assigned Reviews": "Revisiones asignadas",
    "Assigned Date": "Fecha de asignación",
    "Completed Date": "Fecha de completado",
    "Total Assigned": "Total asignado",
    "No reviews assigned": "No hay revisiones asignadas",
    "Individual Reviewer Scores": "Puntuaciones individuales del revisor",
    "Per-Criterion Breakdown": "Desglose por criterio",
    "No reviews completed": "No hay revisiones completadas",
    "Eligibility:": "Elegibilidad:",
    "Application Deadline:": "Fecha límite de solicitud:",
    "(Overdue)": "(Vencido)",
    "Comments (optional)": "Comentarios (opcional)",
    "My Application: Draft": "Mi solicitud: Borrador",
    "My Application: Submitted": "Mi solicitud: Enviada",
    "My Application: Under Review": "Mi solicitud: En revisión",
    "My Application: Revision Requested": "Mi solicitud: Revisión solicitada",
    "My Application: Approved": "Mi solicitud: Aprobada",
    "My Application: Denied": "Mi solicitud: Denegada",
    "My Application: Withdrawn": "Mi solicitud: Retirada",
    "Submit SF-425": "Enviar SF-425",
    "View SF-425 Form": "Ver formulario SF-425",
    "No report data has been entered.": "No se han ingresado datos del informe.",
    "Add comments about this report...": "Agregar comentarios sobre este informe...",
    "Provide feedback for this criterion...": "Proporcionar retroalimentación para este criterio...",
}


def translate_po_file(filepath):
    """Parse and translate a .po file using the dictionary."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix header
    content = content.replace('#, fuzzy\nmsgid ""\nmsgstr ""', 'msgid ""\nmsgstr ""')
    content = content.replace('"Language: \\n"', '"Language: es\\n"')
    content = content.replace(
        '"Plural-Forms: nplurals=3; plural=n == 1 ? 0 : n != 0 && n % 1000000 == 0 ? 1 : 2;\\n"',
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"'
    )

    lines = content.split('\n')
    result = []
    i = 0
    in_header = True
    current_msgid = None
    current_msgctxt = None

    while i < len(lines):
        line = lines[i]

        # Track when we exit the header
        if in_header and line.startswith('#:'):
            in_header = False

        # Track msgctxt
        if line.startswith('msgctxt '):
            current_msgctxt = line[9:-1]  # strip msgctxt "..."
            result.append(line)
            i += 1
            continue

        # Found a msgid line
        if line.startswith('msgid "') and not line.startswith('msgid ""'):
            msgid_str = line[7:-1]  # strip msgid "..."
            result.append(line)
            i += 1

            # Check for multiline msgid
            while i < len(lines) and lines[i].startswith('"'):
                msgid_str += lines[i][1:-1]
                result.append(lines[i])
                i += 1

            # Now we should be at msgstr line
            if i < len(lines) and lines[i].startswith('msgstr "'):
                existing_msgstr = lines[i][8:-1]

                # Skip multiline existing msgstr content
                msgstr_lines_to_skip = []
                j = i + 1
                while j < len(lines) and lines[j].startswith('"'):
                    existing_msgstr += lines[j][1:-1]
                    j += 1

                if existing_msgstr:
                    # Already translated, keep it
                    result.append(lines[i])
                    for k in range(i + 1, j):
                        result.append(lines[k])
                    i = j
                else:
                    # Need translation
                    translation = TRANSLATIONS.get(msgid_str)

                    if translation is None:
                        # Try to find a partial match or keep English
                        translation = find_translation(msgid_str)

                    # Escape unescaped quotes in translation
                    # The msgid_str from .po file already has \" for embedded quotes,
                    # so only escape truly unescaped quotes (from our dictionary translations)
                    if translation:
                        # First unescape any already-escaped quotes, then re-escape all
                        unescaped = translation.replace('\\"', '"')
                        translation = unescaped.replace('"', '\\"')
                    else:
                        translation = msgid_str

                    result.append(f'msgstr "{translation}"')
                    i = j  # skip any multiline msgstr lines
            else:
                result.append(lines[i])
                i += 1

            current_msgctxt = None
            continue

        # Handle msgid_plural + msgstr[0]/msgstr[1]
        if line.startswith('msgid_plural "'):
            result.append(line)
            i += 1
            # Collect msgstr[0], msgstr[1], etc.
            while i < len(lines) and lines[i].startswith('msgstr['):
                existing = lines[i].split('"', 1)[1].rstrip('"') if '"' in lines[i] else ''
                if not existing:
                    # Keep same as English for now
                    result.append(lines[i])
                else:
                    result.append(lines[i])
                i += 1
            continue

        result.append(line)
        i += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result))

    # Count results
    translated = sum(1 for line in result if line.startswith('msgstr "') and line != 'msgstr ""')
    empty = sum(1 for line in result if line == 'msgstr ""')
    print(f"Translated: {translated}, Still empty: {empty}")


def find_translation(msgid):
    """Try to find a translation by decomposing the string or matching patterns."""
    # Check exact match first
    if msgid in TRANSLATIONS:
        return TRANSLATIONS[msgid]

    # If the string contains python-format specifiers like %(name)s,
    # do NOT attempt partial word replacement — it corrupts the format strings.
    # Just return the English as fallback.
    fmt_pattern = re.compile(r'%\([^)]+\)[sd]|%[sd]|%\d*[sd]|\{[^}]*\}')
    if fmt_pattern.search(msgid):
        return msgid

    # For simple strings without format specifiers, try word-level replacement
    # Only replace whole-word matches to avoid corrupting substrings
    result = msgid
    for en, es in sorted(TRANSLATIONS.items(), key=lambda x: -len(x[0])):
        if len(en) > 3 and en in result:
            # Only replace if it appears as a standalone segment
            # (at word boundaries, not inside another word)
            pattern = re.compile(r'(?<![a-zA-Z])' + re.escape(en) + r'(?![a-zA-Z])')
            result = pattern.sub(es, result)

    if result != msgid:
        return result

    # Return English as fallback (better than empty)
    return msgid


if __name__ == '__main__':
    translate_po_file('locale/es/LC_MESSAGES/django.po')
    print("Translation complete!")
