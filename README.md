# 📅 Sistema de Reserva de Espaços

Sistema web para **solicitação e gerenciamento de reservas de espaços institucionais**, permitindo que professores solicitem horários e administradores aprovem ou recusem as solicitações.

## 🎯 Objetivo

Facilitar o controle de reservas de laboratórios, auditório, biblioteca e outros espaços, evitando conflitos de horários e centralizando o processo em um único sistema.

## ⚙️ Tecnologias

* **Python**
* **Flask**
* **SQLite**
* **SQLAlchemy**
* **HTML5 / CSS3**
* **Bootstrap**
* **SMTP / Flask-Mail**

## ✨ Funcionalidades

* 📅 Solicitação de reservas
* 🏫 Gerenciamento de espaços
* ⚠️ Verificação de conflitos de horário
* 📆 Visualização das reservas em calendário
* 📧 Envio de solicitações e notificações por e-mail
* ✅ Aprovação e recusa de reservas
* 🔐 Área administrativa

## 🚀 Instalação

### 1. Clone o projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd lab-reservas
```

### 2. Crie o ambiente virtual

```bash
python -m venv venv
```

**Windows:**

```bash
venv\Scripts\activate
```

**Linux/macOS:**

```bash
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Copie `.env.example` para `.env` e configure as informações necessárias, principalmente as credenciais de e-mail.

```env
SECRET_KEY=sua-chave-secreta
ADMIN_EMAIL=seu-email
ADMIN_PASSWORD=sua-senha

MAIL_USERNAME=seu-email
MAIL_PASSWORD=sua-senha-de-app
```

### 5. Execute o projeto

```bash
python app.py
```

Acesse:

```text
http://127.0.0.1:5000
```

## 📁 Estrutura

```text
lab-reservas/
├── app.py
├── config.py
├── models.py
├── email_service.py
├── requirements.txt
├── .env.example
├── templates/
└── static/
```

## 👨‍💻 Projeto

Sistema desenvolvido para **gerenciamento de reservas de espaços institucionais** utilizando Python e Flask.
