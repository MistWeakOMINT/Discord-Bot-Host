// Estado da aplicação
const appState = {
    currentUser: null,
    isLoggedIn: false,
    currentMenu: 'configuracoes',
    editor: null,
    editorType: null, // 'planning' ou 'document'
};

const API_URL = 'https://sweet-recreation-railway.up.railway.app/api';
const DISCORD_SERVER_ID = '1499872178039029792';
const DISCORD_CHANNEL_ID = '1518419101242888273';

// Utilitários
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
}

function showLoginOptions() {
    showScreen('login-options-screen');
}

function showError(elementId, message) {
    const errorEl = document.getElementById(elementId);
    if (message) {
        errorEl.textContent = message;
        errorEl.classList.add('show');
    } else {
        errorEl.classList.remove('show');
    }
}

// Auth Functions
async function handleLogin(event) {
    event.preventDefault();
    
    const discordName = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    showError('login-error', '');
    
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ discordName, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Erro ao fazer login');
        }
        
        appState.currentUser = data.user;
        appState.isLoggedIn = true;
        
        // Registrar atividade no Discord
        notifyDiscord(`**Login Realizado**\nNick Site: ${data.user.username}\nNick Discord: ${data.user.discordName}`);
        
        loadUserDashboard();
        showScreen('main-panel');
    } catch (error) {
        showError('login-error', error.message);
    }
}

async function handleRegisterStep1(event) {
    event.preventDefault();
    
    const discordName = document.getElementById('register-discord').value;
    const username = document.getElementById('register-name').value;
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('register-confirm-password').value;
    
    showError('register-error', '');
    
    if (password !== confirmPassword) {
        showError('register-error', 'As senhas não conferem');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/auth/verify-discord`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ discordName })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error('Nick do Discord não encontrado ou inválido');
        }
        
        // Armazenar dados temporários
        sessionStorage.setItem('registerData', JSON.stringify({
            discordName,
            username,
            password
        }));
        
        showScreen('profile-setup-screen');
    } catch (error) {
        showError('register-error', error.message);
    }
}

function openChangeProfilePic() {
    document.getElementById('change-pic-input').click();
}

async function handleRegisterStep2(event) {
    event.preventDefault();
    
    const bio = document.getElementById('profile-bio').value;
    const fileInput = document.getElementById('profile-picture');
    
    showError('profile-error', '');
    
    if (!fileInput.files[0]) {
        showError('profile-error', 'Selecione uma foto de perfil');
        return;
    }
    
    try {
        const registerData = JSON.parse(sessionStorage.getItem('registerData'));
        const formData = new FormData();
        
        formData.append('discordName', registerData.discordName);
        formData.append('username', registerData.username);
        formData.append('password', registerData.password);
        formData.append('bio', bio);
        formData.append('profilePicture', fileInput.files[0]);
        
        const response = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Erro ao criar conta');
        }
        
        // Registrar atividade no Discord
        notifyDiscord(`**Conta Criada**\nNick Site: ${registerData.username}\nNick Discord: ${registerData.discordName}`);
        
        sessionStorage.removeItem('registerData');
        alert('Conta criada com sucesso! Agora faça login.');
        showScreen('login-screen');
    } catch (error) {
        showError('profile-error', error.message);
    }
}

async function updateProfilePic(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    try {
        const formData = new FormData();
        formData.append('profilePicture', file);
        
        const response = await fetch(`${API_URL}/user/profile-picture`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            body: formData
        });
        
        if (!response.ok) throw new Error('Erro ao atualizar foto');
        
        const data = await response.json();
        appState.currentUser.profilePicture = data.profilePicture;
        document.getElementById('sidebar-profile-pic').src = appState.currentUser.profilePicture;
    } catch (error) {
        alert(error.message);
    }
}

async function updateBio() {
    const bio = document.getElementById('config-bio').value;
    
    try {
        const response = await fetch(`${API_URL}/user/bio`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ bio })
        });
        
        if (!response.ok) throw new Error('Erro ao atualizar bio');
        
        appState.currentUser.bio = bio;
        alert('Bio atualizada com sucesso!');
    } catch (error) {
        alert(error.message);
    }
}

function handleLogout() {
    appState.isLoggedIn = false;
    appState.currentUser = null;
    localStorage.removeItem('token');
    showScreen('auth-screen');
}

// UI Functions
function openMenu(menuName) {
    // Remover active de todos os menus
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.menu-content').forEach(content => content.classList.remove('active'));
    
    // Adicionar active ao menu selecionado
    event.target.classList.add('active');
    document.getElementById(`menu-${menuName}`).classList.add('active');
    
    appState.currentMenu = menuName;
}

function changeFontSize(size) {
    document.documentElement.style.fontSize = size + 'px';
    localStorage.setItem('fontSize', size);
}

function changeSiteColor(color) {
    document.documentElement.style.setProperty('--accent-color', color);
    localStorage.setItem('siteColor', color);
}

// Loading
function loadUserDashboard() {
    const user = appState.currentUser;
    
    document.getElementById('sidebar-username').textContent = user.username;
    document.getElementById('sidebar-discord').textContent = `@${user.discordName}`;
    document.getElementById('sidebar-profile-pic').src = user.profilePicture;
    document.getElementById('config-bio').value = user.bio || '';
    
    // Mostrar admin section se for admin
    if (user.isAdmin) {
        document.getElementById('admin-section').style.display = 'block';
    }
    
    loadPlannings();
    loadDocuments();
    
    // Restaurar preferências
    const fontSize = localStorage.getItem('fontSize');
    if (fontSize) changeFontSize(fontSize);
    
    const siteColor = localStorage.getItem('siteColor');
    if (siteColor) changeSiteColor(siteColor);
}

async function loadPlannings() {
    try {
        const response = await fetch(`${API_URL}/planings`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        
        const data = await response.json();
        const list = document.getElementById('planejamentos-list');
        
        list.innerHTML = '<h4>📋 Planejamentos</h4>';
        
        data.plannings.forEach(planning => {
            const card = document.createElement('div');
            card.className = 'item-card' + (planning.restricted ? ' restricted' : '');
            card.textContent = planning.title;
            card.onclick = () => openPlanning(planning);
            list.appendChild(card);
        });
    } catch (error) {
        console.error('Erro ao carregar planejamentos:', error);
    }
}

async function loadDocuments() {
    try {
        const response = await fetch(`${API_URL}/documents`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        
        const data = await response.json();
        const list = document.getElementById('documentos-list');
        
        list.innerHTML = '<h4>📄 Documentos</h4>';
        
        data.documents.forEach(doc => {
            const card = document.createElement('div');
            card.className = 'item-card' + (doc.restricted ? ' restricted' : '');
            card.textContent = doc.title;
            card.onclick = () => openDocument(doc);
            list.appendChild(card);
        });
    } catch (error) {
        console.error('Erro ao carregar documentos:', error);
    }
}

// Editor Functions
function createPlanning() {
    document.getElementById('planning-editor').style.display = 'block';
    appState.editorType = 'planning';
    initializeEditor('editor-planning');
}

function createDocument() {
    document.getElementById('document-editor').style.display = 'block';
    appState.editorType = 'document';
    initializeEditor('editor-document');
}

function initializeEditor(elementId) {
    const editor = document.getElementById(elementId);
    editor.contentEditable = 'true';
    editor.classList.add('active');
    
    // Desabilitar cópia
    editor.addEventListener('copy', (e) => e.preventDefault());
    editor.addEventListener('cut', (e) => e.preventDefault());
}

function cancelPlanning() {
    document.getElementById('planning-editor').style.display = 'none';
    document.getElementById('planning-title').value = '';
    document.getElementById('editor-planning').innerHTML = '';
}

function cancelDocument() {
    document.getElementById('document-editor').style.display = 'none';
    document.getElementById('document-title').value = '';
    document.getElementById('editor-document').innerHTML = '';
}

async function savePlanning() {
    const title = document.getElementById('planning-title').value;
    const content = document.getElementById('editor-planning').innerHTML;
    
    if (!title.trim()) {
        alert('Digite um título para o planejamento');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/planings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ title, content })
        });
        
        if (!response.ok) throw new Error('Erro ao salvar planejamento');
        
        notifyDiscord(`**Planejamento Criado**\nAutor: ${appState.currentUser.username} (@${appState.currentUser.discordName})\nTítulo: ${title}`);
        
        cancelPlanning();
        loadPlannings();
        alert('Planejamento salvo com sucesso!');
    } catch (error) {
        alert(error.message);
    }
}

async function saveDocument() {
    const title = document.getElementById('document-title').value;
    const content = document.getElementById('editor-document').innerHTML;
    
    if (!title.trim()) {
        alert('Digite um título para o documento');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/documents`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ title, content })
        });
        
        if (!response.ok) throw new Error('Erro ao salvar documento');
        
        notifyDiscord(`**Documento Criado**\nAutor: ${appState.currentUser.username} (@${appState.currentUser.discordName})\nTítulo: ${title}`);
        
        cancelDocument();
        loadDocuments();
        alert('Documento salvo com sucesso!');
    } catch (error) {
        alert(error.message);
    }
}

async function openPlanning(planning) {
    notifyDiscord(`**Planejamento Acessado**\nUsuário: ${appState.currentUser.username} (@${appState.currentUser.discordName})\nPlanejamento: ${planning.title}`);
    alert(`Abrindo: ${planning.title}\n\n${planning.content.substring(0, 100)}...`);
}

async function openDocument(doc) {
    notifyDiscord(`**Documento Acessado**\nUsuário: ${appState.currentUser.username} (@${appState.currentUser.discordName})\nDocumento: ${doc.title}`);
    alert(`Abrindo: ${doc.title}\n\n${doc.content.substring(0, 100)}...`);
}

// Admin Functions
function openAdminModal(action) {
    const modal = document.getElementById('admin-modal');
    const body = document.getElementById('admin-modal-body');
    
    modal.style.display = 'flex';
    
    let content = '';
    
    switch(action) {
        case 'add-admin':
            content = `
                <h3>Adicionar Admin</h3>
                <input type="text" id="admin-username" placeholder="Nick do Discord">
                <button class="btn-primary" onclick="performAdminAction('add-admin')">Adicionar</button>
            `;
            break;
        case 'add-restricted':
            content = `
                <h3>Adicionar Acesso à Área Restrita</h3>
                <input type="text" id="admin-username" placeholder="Nick do Discord">
                <button class="btn-primary" onclick="performAdminAction('add-restricted')">Adicionar</button>
            `;
            break;
        case 'ban-members':
            content = `
                <h3>Banir Membros</h3>
                <input type="text" id="admin-username" placeholder="Nick do Discord">
                <button class="btn-danger" onclick="performAdminAction('ban-members')">Banir</button>
            `;
            break;
        case 'add-ctr':
            content = `
                <h3>Adicionar Membro C ITR</h3>
                <input type="text" id="admin-username" placeholder="Nick do Discord">
                <button class="btn-primary" onclick="performAdminAction('add-ctr')">Adicionar</button>
            `;
            break;
        case 'add-cai':
            content = `
                <h3>Adicionar Membro CAI</h3>
                <input type="text" id="admin-username" placeholder="Nick do Discord">
                <button class="btn-primary" onclick="performAdminAction('add-cai')">Adicionar</button>
            `;
            break;
    }
    
    body.innerHTML = content;
}

function closeAdminModal() {
    document.getElementById('admin-modal').style.display = 'none';
}

async function performAdminAction(action) {
    const username = document.getElementById('admin-username').value;
    
    if (!username.trim()) {
        alert('Digite um nick válido');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/admin/${action}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ targetUsername: username })
        });
        
        if (!response.ok) throw new Error('Erro ao realizar ação');
        
        notifyDiscord(`**Ação Admin: ${action}**\nAdmin: ${appState.currentUser.username}\nAlvo: ${username}`);
        
        closeAdminModal();
        alert('Ação realizada com sucesso!');
    } catch (error) {
        alert(error.message);
    }
}

// Discord Notification
async function notifyDiscord(message) {
    try {
        // Esta função será implementada no backend
        await fetch(`${API_URL}/discord/notify`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                message,
                serverId: DISCORD_SERVER_ID,
                channelId: DISCORD_CHANNEL_ID
            })
        });
    } catch (error) {
        console.error('Erro ao notificar Discord:', error);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Verificar se já está logado
    const token = localStorage.getItem('token');
    if (token) {
        // Tentar restaurar sessão
        // appState.currentUser = JSON.parse(localStorage.getItem('user'));
        // loadUserDashboard();
        // showScreen('main-panel');
    }
});
