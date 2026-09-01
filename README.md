# SmartZen CRM Consignados

CRM em Flask para cadastro de clientes e propostas de crédito consignado.

## Dados do cliente
- Nome
- Telefone
- CPF/CNPJ
- E-mail
- Cidade
- Origem
- Status
- Observações

## Dados da proposta
- Operador
- Nome do cliente (vinculado)
- Telefone do cliente (vinculado)
- Convênio
- Banco
- CPF do cliente (vinculado)
- Número da proposta
- Data da proposta
- Valor da comissão
- Status
- Tipo de operação
- Observações

## Recursos
- Login
- Dashboard
- Clientes
- Múltiplas propostas por cliente
- Busca e filtros
- WhatsApp
- Exportação CSV de clientes
- Exportação CSV de propostas
- Layout responsivo
- Preparado para Railway

## Login inicial
Usuário: admin
Senha: admin123

## Rodar no Windows
```powershell
py -m pip install -r requirements.txt
py app.py
```

Acesse:
http://127.0.0.1:5000

## Railway
Configure:
- SECRET_KEY
- ADMIN_USER
- ADMIN_PASSWORD
- SMARTZEN_URL (opcional)

Para produção com maior volume, recomendamos PostgreSQL.
