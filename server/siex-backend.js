const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const Discord = require('discord.js');
require('dotenv').config();

const app = express();
app.use(express.json());

// Configuração de upload
const upload = multer({ 
    dest: 'uploads/',
    limits: { fileSize: 10 * 1024 * 1024 } // 10MB
});

// Database (usar MongoDB em produção)
const users = new Map();
const plannings = new Map();
const documents = new Map();

const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key';
const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const DISCORD_SERVER_ID = '1499872178039029792';
const DISCORD_CHANNEL_ID = '1518419101242888273';

// Discord Bot
const discordClient = new Discord.Client({ intents: ['Guilds', 'DirectMessages'] });

discordClient.once('ready', () => {
    console.log(`Discord Bot conectado como ${discordClient.user.tag}`);
});

discordClient.login(DISCORD_TOKEN);

// Middleware de autenticação
function authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];
    
    if (!token) return res.sendStatus(401);
    
    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) return res.sendStatus(403);
        req.user = user;
        next();
    });
}

// Auth Routes
app.post('/api/auth/verify-discord', async (req, res) => {
    try {
        const { discordName } = req.body;
        
        // Verificar se o Discord existe (em produção, usar Discord API)
        // Por enquanto, apenas validar formato
        if (!discordName || discordName.length < 2) {
            return res.status(400).json({ message: 'Nick do Discord inválido' });
        }
        
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

app.post('/api/auth/register', upload.single('profilePicture'), async (req, res) => {
    try {
        const { discordName, username, password, bio } = req.body;
        
        if (!discordName || !username || !password) {
            return res.status(400).json({ message: 'Dados incompletos' });
        }
        
        if (Array.from(users.values()).some(u => u.username === username)) {
            return res.status(400).json({ message: 'Nome de usuário já existe' });
        }
        
        // Hash da senha
        const hashedPassword = await bcrypt.hash(password, 10);
        
        // Salvar foto de perfil
        let profilePicture = '/default-avatar.png';
        if (req.file) {
            profilePicture = `/uploads/${req.file.filename}`;
        }
        
        const userId = Date.now().toString();
        const user = {
            id: userId,
            discordName,
            username,
            password: hashedPassword,
            bio: bio || '',
            profilePicture,
            isAdmin: false,
            hasRestricted: false,
            roles: [],
            createdAt: new Date()
        };
        
        users.set(userId, user);
        
        res.json({
            message: 'Conta criada com sucesso',
            user: {
                id: user.id,
                username: user.username,
                discordName: user.discordName,
                profilePicture: user.profilePicture
            }
        });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

app.post('/api/auth/login', async (req, res) => {
    try {
        const { discordName, password } = req.body;
        
        const user = Array.from(users.values()).find(u => u.discordName === discordName);
        
        if (!user) {
            return res.status(400).json({ message: 'Nick do Discord não encontrado' });
        }
        
        const validPassword = await bcrypt.compare(password, user.password);
        
        if (!validPassword) {
            return res.status(400).json({ message: 'Senha incorreta' });
        }
        
        const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET, { expiresIn: '24h' });
        
        res.json({
            token,
            user: {
                id: user.id,
                username: user.username,
                discordName: user.discordName,
                bio: user.bio,
                profilePicture: user.profilePicture,
                isAdmin: user.isAdmin
            }
        });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// User Routes
app.post('/api/user/profile-picture', authenticateToken, upload.single('profilePicture'), async (req, res) => {
    try {
        const user = users.get(req.user.id);
        
        if (!user) {
            return res.status(404).json({ message: 'Usuário não encontrado' });
        }
        
        if (req.file) {
            user.profilePicture = `/uploads/${req.file.filename}`;
        }
        
        res.json({ profilePicture: user.profilePicture });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

app.post('/api/user/bio', authenticateToken, (req, res) => {
    try {
        const { bio } = req.body;
        const user = users.get(req.user.id);
        
        if (!user) {
            return res.status(404).json({ message: 'Usuário não encontrado' });
        }
        
        user.bio = bio;
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// Planning Routes
app.post('/api/planings', authenticateToken, (req, res) => {
    try {
        const { title, content } = req.body;
        const user = users.get(req.user.id);
        
        if (!user) {
            return res.status(404).json({ message: 'Usuário não encontrado' });
        }
        
        const planningId = Date.now().toString();
        const planning = {
            id: planningId,
            userId: req.user.id,
            author: user.username,
            title,
            content,
            restricted: false,
            createdAt: new Date()
        };
        
        plannings.set(planningId, planning);
        
        res.json({ id: planningId, message: 'Planejamento salvo' });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

app.get('/api/planings', authenticateToken, (req, res) => {
    try {
        const userPlannings = Array.from(plannings.values())
            .filter(p => !p.restricted || p.userId === req.user.id);
        
        res.json({ plannings: userPlannings });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// Document Routes
app.post('/api/documents', authenticateToken, (req, res) => {
    try {
        const { title, content } = req.body;
        const user = users.get(req.user.id);
        
        if (!user) {
            return res.status(404).json({ message: 'Usuário não encontrado' });
        }
        
        const docId = Date.now().toString();
        const doc = {
            id: docId,
            userId: req.user.id,
            author: user.username,
            title,
            content,
            restricted: false,
            createdAt: new Date()
        };
        
        documents.set(docId, doc);
        
        res.json({ id: docId, message: 'Documento salvo' });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

app.get('/api/documents', authenticateToken, (req, res) => {
    try {
        const userDocs = Array.from(documents.values())
            .filter(d => !d.restricted || d.userId === req.user.id);
        
        res.json({ documents: userDocs });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// Admin Routes
app.post('/api/admin/:action', authenticateToken, async (req, res) => {
    try {
        const adminUser = users.get(req.user.id);
        
        if (!adminUser || !adminUser.isAdmin) {
            return res.status(403).json({ message: 'Acesso negado' });
        }
        
        const { targetUsername } = req.body;
        const targetUser = Array.from(users.values()).find(u => u.username === targetUsername);
        
        if (!targetUser) {
            return res.status(404).json({ message: 'Usuário não encontrado' });
        }
        
        const action = req.params.action;
        
        switch(action) {
            case 'add-admin':
                targetUser.isAdmin = true;
                break;
            case 'add-restricted':
                targetUser.hasRestricted = true;
                break;
            case 'ban-members':
                targetUser.banned = true;
                break;
            case 'add-ctr':
                targetUser.roles = targetUser.roles || [];
                if (!targetUser.roles.includes('C_ITR')) {
                    targetUser.roles.push('C_ITR');
                }
                break;
            case 'add-cai':
                targetUser.roles = targetUser.roles || [];
                if (!targetUser.roles.includes('CAI')) {
                    targetUser.roles.push('CAI');
                }
                break;
        }
        
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// Discord Notification
app.post('/api/discord/notify', authenticateToken, async (req, res) => {
    try {
        const { message, serverId, channelId } = req.body;
        
        const guild = await discordClient.guilds.fetch(serverId);
        const channel = await guild.channels.fetch(channelId);
        
        if (channel && channel.isTextBased()) {
            await channel.send({
                content: message,
                embeds: [{
                    color: 0x89b4fa,
                    timestamp: new Date()
                }]
            });
        }
        
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// Static files
app.use(express.static('docs'));
app.use('/uploads', express.static('uploads'));

// 404
app.use((req, res) => {
    res.status(404).json({ message: 'Rota não encontrada' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Servidor SIEx rodando na porta ${PORT}`);
});