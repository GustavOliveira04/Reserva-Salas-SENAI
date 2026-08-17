# Reserva de Laboratórios

Sistema web em Flask + Bootstrap para solicitação e aprovação de reservas de laboratórios, auditório e biblioteca.

## Funcionalidades

- Calendário mensal com agendamentos confirmados
- Formulário de solicitação para professores
- Envio de e-mail ao administrador com botões de aceitar/recusar
- Notificação automática ao professor após aprovação ou recusa
- Detecção de conflito de horário ao aprovar

## Espaços disponíveis

- Laboratório 1, 2 e 3
- Auditório
- Biblioteca

## Instalação

```bash
cd lab-reservas
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite o arquivo `.env` com suas credenciais SMTP e o e-mail do administrador.

## Executar

```bash
python app.py
```

Acesse: http://127.0.0.1:5000

## Configuração de e-mail

Configure no `.env`:

- `ADMIN_EMAIL` — quem recebe as solicitações
- `MAIL_USERNAME` / `MAIL_PASSWORD` — credenciais SMTP
- `BASE_URL` — URL pública do site (necessária para os links nos e-mails)

> **Gmail:** use uma [senha de app](https://support.google.com/accounts/answer/185833), não a senha normal da conta.

## Fluxo

1. Professor preenche o formulário em `/reservar`
2. Administrador recebe e-mail com detalhes e links **Aceitar** / **Recusar**
3. Se aceito → reserva aparece no calendário e professor recebe confirmação
4. Se recusado → professor recebe e-mail de recusa

## Estrutura

```
lab-reservas/
├── app.py              # Rotas e lógica principal
├── config.py           # Configurações
├── models.py           # Modelos do banco
├── email_service.py    # Envio de e-mails
├── templates/          # HTML (Bootstrap)
└── static/css/         # Estilos do calendário
```
