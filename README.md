# SIEx - Sistema de Documentos e Seções

**SIEx** é um sistema de gerenciamento de documentos, planejamentos e seções com integração completa ao Discord. Projetado para organizar investigações, operações e documentação com controle granular de acesso.

## 🎯 Funcionalidades

### 🔐 Autenticação
- Login/Registro com verificação de Nick Discord
- Senhas hashadas com bcrypt
- JWT para autenticação
- Reset de senha a cada quinzena (automático via bot)
- Verificação de segurança contra contas suspeitas

### 👤 Perfil do Usuário
- Foto de perfil customizável
- Bio personalizável
- Configurações de preferência (tamanho de letra, cor do site)
- Gerenciamento de permissões

### 📄 Documentos
- Editor de texto rico completo (similar ao Google Docs)
- Criar e gerenciar documentos gerais
- Compartilhamento com controle de acesso
- Proteção contra cópia (Ctrl+C bloqueado)
- Proteção contra screenshots (tela fica escura)
- Logs de acesso no Discord

### 📋 Planejamentos
- Editor dedicado para planejamentos de investigações e operações
- Compartilhamento restrito (C_ITR, CAI, Admin)
- Visibilidade baseada em roles
- Logs de criação e acesso

### 🛡️ Controle de Acesso
- **Tags de Acesso:**
  - `C_ITR` - Setor de Investigação Tática
  - `CAI` - Setor de Análise de Inteligência
  - `Admin` - Administradores (apenas MistWeakOMINT inicialmente)

### ⚙️ Administração
- Adicionar Admins
- Conceder acesso à Área Restrita
- Banir membros
- Atribuir tags C_ITR e CAI
- Reset periódico de senhas

### 🤖 Integração Discord
- Notificações em tempo real de:
  - Criação de contas
  - Login de usuários
  - Acesso a documentos/planejamentos
  - Ações administrativas
  - Mudanças de perfil
- Bot envia novas senhas via DM (24h de duração)
- Logs centralizados em canal dedicado

## 🚀 Instalação

### Pré-requisitos
- Node.js 16+
- npm ou yarn
- Discord Bot Token

### Passos

1. **Clone o repositório:**
```bash
git clone https://github.com/MistWeakOMINT/Discord-Bot-Host.git
cd Discord-Bot-Host
```

2. **Instale as dependências:**
```bash
npm install
```

3. **Configure o arquivo `.env`:**
```bash
cp .env.example .env
```

Edite o `.env` com suas configurações:
```env
DISCORD_TOKEN=seu_token_aqui
DISCORD_SERVER_ID=1499872178039029792
DISCORD_CHANNEL_ID=1518419101242888273
PORT=3000
JWT_SECRET=sua_chave_secreta_aqui
```

4. **Inicie o servidor:**
```bash
# Desenvolvimento
npm run dev

# Produção
npm start
```

5. **Acesse o site:**
```
http://localhost:3000
```

## 📁 Estrutura do Projeto

```
Discord-Bot-Host/
├── docs/                      # Frontend (HTML/CSS/JS)
│   ├── index.html            # Página principal
│   ├── styles.css            # Estilos
│   └── app.js                # Lógica do cliente
├── server/
│   └── siex-backend.js       # Backend Express + Discord.js
├── uploads/                  # Fotos de perfil
├── package.json             # Dependências
├── .env.example             # Configuração de exemplo
└── README.md                # Este arquivo
```

## 🔒 Segurança

### Proteção de Dados
- ✅ Senhas hashadas com bcrypt
- ✅ Tokens JWT com expiração
- ✅ Proteção contra copy/paste de documentos
- ✅ Proteção contra screenshots (tela escurecida)
- ✅ Sem posibilidade de salvar/exportar conteúdo

### Fluxo de Segurança
1. Novo usuário cria conta
2. Bot verifica Nick Discord no servidor
3. Se não existir, login recusado
4. Acesso a documentos registrado no Discord
5. Senhas resetadas a cada quinzena
6. Novas senhas enviadas via DM do bot (24h)
7. Admin pode banir usuários suspeitos imediatamente

## 📝 Uso

### Para Usuários Normais
1. **Criar Conta:** Clique em "Criar Conta" → Preencha dados → Adicione foto e bio
2. **Acessar Documentos:** Menu "Documentos" → Escolha um documento existente
3. **Criar Documento:** Clique "Criar Documento" → Use editor → Salve
4. **Acessar Planejamentos:** Menu "Área Restrita" (se tiver acesso)

### Para Administradores
1. **Configurações → Administração**
2. Gerencie usuários, roles e acesso
3. Monitor atividades via canal Discord

## 🎨 Personalização

### Temas
- Customize cores no CSS
- Padrão: Catppuccin Mocha (tema dark)

### Fonte
- Ajuste tamanho de letra nas Configurações (12-20px)
- Salvo localmente no navegador

## 🔄 Fluxo de Reset de Senha

**A cada quinzena:**
1. Bot gera nova senha
2. Envia via DM para o usuário com aviso de segurança
3. Usuário faz login com nova senha
4. 24h após envio, bot deleta a mensagem por segurança
5. Usuário é deslogado automaticamente

## 🐛 Troubleshooting

### "Nick do Discord não encontrado"
- Verifique se seu nick está correto
- Certifique-se que você está no servidor do SIEx

### "Erro ao fazer login"
- Verifique suas credenciais
- Se esqueceu a senha, aguarde o reset automático
- Contate um admin

### Screenshots ficam pretos
- Isso é intencional para segurança
- Use o editor do site para copiar conteúdo entre abas

## 📞 Suporte

Para problemas ou sugestões, entre em contato com MistWeakOMINT no Discord.

## 📄 Licença

MIT - Veja LICENSE para detalhes

---

**Desenvolvido com ❤️ para o SIEx**