// API Base URL
const API_BASE = '';

// Cargar datos al iniciar
document.addEventListener('DOMContentLoaded', function() {
    loadConfiguration();
    loadStatistics();
    loadSellers();
    startLogsPolling();
    
    // Actualizar stats cada 30 segundos
    setInterval(loadStatistics, 30000);
});

// ============= CONFIGURACIÓN =============

async function loadConfiguration() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/config`);
        const config = await response.json();
        
        // WhatsApp
        document.getElementById('accessToken').value = config.whatsapp?.access_token || '';
        document.getElementById('phoneNumberId').value = config.whatsapp?.phone_number_id || '';
        document.getElementById('businessAccountId').value = config.whatsapp?.business_account_id || '';
        document.getElementById('verifyToken').value = config.whatsapp?.verify_token || '';
        
        // IA
        document.getElementById('anthropicKey').value = config.ai?.api_key || '';
        document.getElementById('aiModel').value = config.ai?.model || 'claude-3-5-haiku-20241022';
        document.getElementById('aiEnabled').checked = config.ai?.enabled !== false;
        document.getElementById('minLeadScore').value = config.ai?.min_lead_score || 7;
        
        // Negocio
        document.getElementById('businessName').value = config.business?.name || 'ARCOSUM';
        document.getElementById('businessPhone').value = config.business?.phone || '';
        document.getElementById('businessEmail').value = config.business?.email || '';
        document.getElementById('businessWebsite').value = config.business?.website || '';
        document.getElementById('hoursWeekday').value = config.business?.hours_weekday || '';
        document.getElementById('hoursSaturday').value = config.business?.hours_saturday || '';
        
        // System Prompt
        document.getElementById('systemPrompt').value = config.ai?.system_prompt || '';
        
    } catch (error) {
        console.error('Error cargando configuración:', error);
        showAlert('Error cargando configuración', 'error');
    }
}

// Guardar configuración de WhatsApp
document.getElementById('whatsappForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const config = {
        access_token: document.getElementById('accessToken').value,
        phone_number_id: document.getElementById('phoneNumberId').value,
        business_account_id: document.getElementById('businessAccountId').value,
        verify_token: document.getElementById('verifyToken').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/config/whatsapp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            showAlert('Configuración de WhatsApp guardada correctamente', 'success');
        } else {
            throw new Error('Error al guardar');
        }
    } catch (error) {
        showAlert('Error guardando configuración de WhatsApp', 'error');
    }
});

// Guardar configuración de IA
document.getElementById('aiForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const config = {
        api_key: document.getElementById('anthropicKey').value,
        model: document.getElementById('aiModel').value,
        enabled: document.getElementById('aiEnabled').checked,
        min_lead_score: parseInt(document.getElementById('minLeadScore').value)
    };
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/config/ai`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            showAlert('Configuración de IA guardada correctamente', 'success');
        } else {
            throw new Error('Error al guardar');
        }
    } catch (error) {
        showAlert('Error guardando configuración de IA', 'error');
    }
});

// Guardar información del negocio
document.getElementById('businessForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const config = {
        name: document.getElementById('businessName').value,
        phone: document.getElementById('businessPhone').value,
        email: document.getElementById('businessEmail').value,
        website: document.getElementById('businessWebsite').value,
        hours_weekday: document.getElementById('hoursWeekday').value,
        hours_saturday: document.getElementById('hoursSaturday').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/config/business`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            showAlert('Información del negocio guardada', 'success');
        } else {
            throw new Error('Error al guardar');
        }
    } catch (error) {
        showAlert('Error guardando información del negocio', 'error');
    }
});

// Guardar System Prompt
async function saveSystemPrompt() {
    const prompt = document.getElementById('systemPrompt').value;
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/config/prompt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ system_prompt: prompt })
        });
        
        if (response.ok) {
            showAlert('Prompt de IA guardado correctamente', 'success');
        } else {
            throw new Error('Error al guardar');
        }
    } catch (error) {
        showAlert('Error guardando prompt', 'error');
    }
}

// ============= ESTADÍSTICAS =============

async function loadStatistics() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/stats`);
        const stats = await response.json();
        
        document.getElementById('totalUsers').textContent = stats.total_users || 0;
        document.getElementById('messagesToday').textContent = stats.messages_today || 0;
        document.getElementById('qualifiedLeads').textContent = stats.qualified_leads || 0;
        document.getElementById('pendingQuotes').textContent = stats.pending_quotes || 0;
        
        // Actualizar estado
        const badge = document.getElementById('statusBadge');
        if (stats.status === 'online') {
            badge.className = 'status-badge';
            badge.textContent = '● ONLINE';
        } else {
            badge.className = 'status-badge offline';
            badge.textContent = '● OFFLINE';
        }
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
    }
}

// ============= VENDEDORES =============

async function loadSellers() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/sellers`);
        const sellers = await response.json();
        
        const container = document.getElementById('sellersList');
        container.innerHTML = '';
        
        if (sellers.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No hay vendedores configurados</p>';
            return;
        }
        
        sellers.sort((a, b) => b.priority - a.priority);
        
        sellers.forEach(seller => {
            const sellerDiv = document.createElement('div');
            sellerDiv.className = 'seller-item';
            sellerDiv.innerHTML = `
                <div class="seller-info">
                    <strong>${seller.name}</strong><br>
                    <small>📱 ${seller.phone}</small>
                    ${seller.email ? `<br><small>📧 ${seller.email}</small>` : ''}
                </div>
                <span class="seller-priority">Prioridad: ${seller.priority}</span>
                <div class="seller-actions">
                    <button class="btn btn-secondary btn-small" onclick="editSeller(${seller.id})">✏️ Editar</button>
                    <button class="btn btn-danger btn-small" onclick="deleteSeller(${seller.id})">🗑️</button>
                </div>
            `;
            container.appendChild(sellerDiv);
        });
    } catch (error) {
        console.error('Error cargando vendedores:', error);
    }
}

// Modal de vendedor
function openAddSellerModal() {
    document.getElementById('sellerModal').style.display = 'block';
    document.getElementById('addSellerForm').reset();
}

function closeAddSellerModal() {
    document.getElementById('sellerModal').style.display = 'none';
}

// Agregar vendedor
document.getElementById('addSellerForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const seller = {
        name: document.getElementById('sellerName').value,
        phone: document.getElementById('sellerPhone').value,
        email: document.getElementById('sellerEmail').value,
        priority: parseInt(document.getElementById('sellerPriority').value),
        active: document.getElementById('sellerActive').checked
    };
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/sellers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(seller)
        });
        
        if (response.ok) {
            showAlert('Vendedor agregado correctamente', 'success');
            closeAddSellerModal();
            loadSellers();
        } else {
            throw new Error('Error al agregar');
        }
    } catch (error) {
        showAlert('Error agregando vendedor', 'error');
    }
});

// Eliminar vendedor
async function deleteSeller(id) {
    if (!confirm('¿Estás seguro de eliminar este vendedor?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/sellers/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showAlert('Vendedor eliminado', 'success');
            loadSellers();
        } else {
            throw new Error('Error al eliminar');
        }
    } catch (error) {
        showAlert('Error eliminando vendedor', 'error');
    }
}

// ============= LOGS =============

let logsBuffer = [];

async function startLogsPolling() {
    // Conectar a logs (simulado - en producción usar WebSocket)
    setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/admin/logs?last=10`);
            const logs = await response.json();
            
            logs.forEach(log => addLogEntry(log));
        } catch (error) {
            console.error('Error cargando logs:', error);
        }
    }, 5000);
}

function addLogEntry(log) {
    const container = document.getElementById('logsContainer');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    const levelClass = `log-level-${log.level.toLowerCase()}`;
    
    entry.innerHTML = `
        <span class="log-timestamp">[${log.timestamp}]</span>
        <span class="${levelClass}">[${log.level}]</span>
        ${log.message}
    `;
    
    container.appendChild(entry);
    
    // Mantener solo últimos 50 logs
    while (container.children.length > 50) {
        container.removeChild(container.firstChild);
    }
    
    // Auto-scroll
    container.scrollTop = container.scrollHeight;
}

function clearLogs() {
    document.getElementById('logsContainer').innerHTML = '';
    showAlert('Logs limpiados', 'success');
}

// ============= UTILIDADES =============

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    document.querySelector('.container').insertBefore(alertDiv, document.querySelector('.header').nextSibling);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Cerrar modal al hacer clic fuera
window.onclick = function(event) {
    const modal = document.getElementById('sellerModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}