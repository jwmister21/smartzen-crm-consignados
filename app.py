import os
import csv
import io
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "smartzen-dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///smartzen_crm.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace(
        "postgres://", "postgresql://", 1
    )

db = SQLAlchemy(app)
SMARTZEN_URL = os.environ.get("SMARTZEN_URL", "#")

CLIENT_STATUS = ["Novo", "Em contato", "Interessado", "Cliente", "Inativo"]
PROPOSAL_STATUS = ["Digitada", "Em análise", "Aprovada", "Paga", "Pendente", "Cancelada", "Recusada"]
SOURCE_OPTIONS = ["Indicação", "WhatsApp", "Instagram", "Facebook", "Site", "Ligação", "SmartZen", "Outro"]
OPERATION_TYPES = ["Portabilidade", "Refinanciamento", "Contrato novo", "Empréstimo pessoal", "Empréstimo na conta de luz", "Outro"]


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(140))
    document = db.Column(db.String(30))
    city = db.Column(db.String(100))
    source = db.Column(db.String(80))
    status = db.Column(db.String(30), default="Novo")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    proposals = db.relationship(
        "Proposal",
        backref="client",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Proposal.created_at.desc()"
    )


class Proposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)

    operator = db.Column(db.String(120))
    agreement = db.Column(db.String(120))         # Convênio
    bank = db.Column(db.String(120))
    proposal_number = db.Column(db.String(80))
    proposal_date = db.Column(db.Date)
    commission_value = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(40), default="Digitada")
    operation_type = db.Column(db.String(80))
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "SMARTZEN_URL": SMARTZEN_URL,
        "CLIENT_STATUS": CLIENT_STATUS,
        "PROPOSAL_STATUS": PROPOSAL_STATUS,
        "SOURCE_OPTIONS": SOURCE_OPTIONS,
        "OPERATION_TYPES": OPERATION_TYPES,
    }


@app.before_request
def create_tables_and_admin():
    db.create_all()
    admin_user = os.environ.get("ADMIN_USER", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = User.query.filter_by(username=admin_user).first()
    if not existing:
        user = User(username=admin_user)
        user.set_password(admin_password)
        db.session.add(user)
        db.session.commit()


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("dashboard"))

        flash("Usuário ou senha inválidos.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    total_clients = Client.query.count()
    total_proposals = Proposal.query.count()
    approved = Proposal.query.filter(Proposal.status.in_(["Aprovada", "Paga"])).count()
    pending = Proposal.query.filter(Proposal.status.in_(["Em análise", "Pendente", "Digitada"])).count()

    paid_proposals = Proposal.query.filter_by(status="Paga").all()
    total_commission = sum((p.commission_value or 0) for p in paid_proposals)

    recent_proposals = Proposal.query.order_by(Proposal.created_at.desc()).limit(10).all()

    return render_template(
        "dashboard.html",
        total_clients=total_clients,
        total_proposals=total_proposals,
        approved=approved,
        pending=pending,
        total_commission=total_commission,
        recent_proposals=recent_proposals,
    )


@app.route("/clientes")
@login_required
def clients():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Client.name.ilike(like),
                Client.phone.ilike(like),
                Client.email.ilike(like),
                Client.document.ilike(like),
                Client.city.ilike(like),
            )
        )

    if status:
        query = query.filter_by(status=status)

    items = query.order_by(Client.created_at.desc()).all()
    return render_template("clients.html", clients=items, q=q, selected_status=status)


@app.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def new_client():
    if request.method == "POST":
        client = Client(
            name=request.form.get("name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            document=request.form.get("document", "").strip(),
            city=request.form.get("city", "").strip(),
            source=request.form.get("source", "").strip(),
            status=request.form.get("status", "Novo").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        if not client.name:
            flash("O nome do cliente é obrigatório.", "danger")
            return render_template("client_form.html", client=client, title="Novo cliente")

        db.session.add(client)
        db.session.commit()
        flash("Cliente cadastrado com sucesso.", "success")
        return redirect(url_for("new_proposal", client_id=client.id))

    return render_template("client_form.html", client=None, title="Novo cliente")


@app.route("/clientes/<int:client_id>")
@login_required
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template("client_detail.html", client=client)


@app.route("/clientes/<int:client_id>/editar", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)

    if request.method == "POST":
        client.name = request.form.get("name", "").strip()
        client.phone = request.form.get("phone", "").strip()
        client.email = request.form.get("email", "").strip()
        client.document = request.form.get("document", "").strip()
        client.city = request.form.get("city", "").strip()
        client.source = request.form.get("source", "").strip()
        client.status = request.form.get("status", "Novo").strip()
        client.notes = request.form.get("notes", "").strip()

        if not client.name:
            flash("O nome do cliente é obrigatório.", "danger")
            return render_template("client_form.html", client=client, title="Editar cliente")

        db.session.commit()
        flash("Cliente atualizado.", "success")
        return redirect(url_for("client_detail", client_id=client.id))

    return render_template("client_form.html", client=client, title="Editar cliente")


@app.post("/clientes/<int:client_id>/excluir")
@login_required
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash("Cliente excluído.", "success")
    return redirect(url_for("clients"))


@app.route("/propostas")
@login_required
def proposals():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = Proposal.query.join(Client)

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Client.name.ilike(like),
                Client.document.ilike(like),
                Client.phone.ilike(like),
                Proposal.proposal_number.ilike(like),
                Proposal.operator.ilike(like),
                Proposal.bank.ilike(like),
                Proposal.agreement.ilike(like),
            )
        )

    if status:
        query = query.filter(Proposal.status == status)

    items = query.order_by(Proposal.created_at.desc()).all()
    return render_template("proposals.html", proposals=items, q=q, selected_status=status)


@app.route("/clientes/<int:client_id>/propostas/nova", methods=["GET", "POST"])
@login_required
def new_proposal(client_id):
    client = Client.query.get_or_404(client_id)

    if request.method == "POST":
        date_value = request.form.get("proposal_date", "").strip()
        proposal_date = None
        if date_value:
            try:
                proposal_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            except ValueError:
                pass

        try:
            commission = float(request.form.get("commission_value", "0").replace(".", "").replace(",", "."))
        except ValueError:
            commission = 0.0

        proposal = Proposal(
            client_id=client.id,
            operator=request.form.get("operator", "").strip(),
            agreement=request.form.get("agreement", "").strip(),
            bank=request.form.get("bank", "").strip(),
            proposal_number=request.form.get("proposal_number", "").strip(),
            proposal_date=proposal_date,
            commission_value=commission,
            status=request.form.get("status", "Digitada").strip(),
            operation_type=request.form.get("operation_type", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(proposal)
        db.session.commit()
        flash("Proposta cadastrada com sucesso.", "success")
        return redirect(url_for("client_detail", client_id=client.id))

    return render_template("proposal_form.html", client=client, proposal=None, title="Nova proposta")


@app.route("/propostas/<int:proposal_id>/editar", methods=["GET", "POST"])
@login_required
def edit_proposal(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    client = proposal.client

    if request.method == "POST":
        proposal.operator = request.form.get("operator", "").strip()
        proposal.agreement = request.form.get("agreement", "").strip()
        proposal.bank = request.form.get("bank", "").strip()
        proposal.proposal_number = request.form.get("proposal_number", "").strip()
        proposal.status = request.form.get("status", "Digitada").strip()
        proposal.operation_type = request.form.get("operation_type", "").strip()
        proposal.notes = request.form.get("notes", "").strip()

        date_value = request.form.get("proposal_date", "").strip()
        if date_value:
            try:
                proposal.proposal_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            except ValueError:
                proposal.proposal_date = None
        else:
            proposal.proposal_date = None

        try:
            proposal.commission_value = float(
                request.form.get("commission_value", "0").replace(".", "").replace(",", ".")
            )
        except ValueError:
            proposal.commission_value = 0.0

        db.session.commit()
        flash("Proposta atualizada.", "success")
        return redirect(url_for("client_detail", client_id=client.id))

    return render_template("proposal_form.html", client=client, proposal=proposal, title="Editar proposta")


@app.post("/propostas/<int:proposal_id>/excluir")
@login_required
def delete_proposal(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    client_id = proposal.client_id
    db.session.delete(proposal)
    db.session.commit()
    flash("Proposta excluída.", "success")
    return redirect(url_for("client_detail", client_id=client_id))


@app.route("/exportar-clientes.csv")
@login_required
def export_clients_csv():
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Nome", "Telefone", "E-mail", "CPF/CNPJ", "Cidade", "Origem", "Status", "Observações", "Cadastro"])
    for c in Client.query.order_by(Client.id.asc()).all():
        writer.writerow([
            c.id, c.name, c.phone, c.email, c.document, c.city,
            c.source, c.status, c.notes,
            c.created_at.strftime("%d/%m/%Y %H:%M") if c.created_at else ""
        ])
    data = "\ufeff" + output.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=clientes_smartzen.csv"})


@app.route("/exportar-propostas.csv")
@login_required
def export_proposals_csv():
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Operador", "Nome do Cliente", "Telefone do Cliente", "Convênio",
        "Banco", "CPF do Cliente", "Número da Proposta", "Data da Proposta",
        "Valor da Comissão", "Status", "Tipo de Operação", "Observações"
    ])

    for p in Proposal.query.order_by(Proposal.id.asc()).all():
        writer.writerow([
            p.operator or "",
            p.client.name,
            p.client.phone or "",
            p.agreement or "",
            p.bank or "",
            p.client.document or "",
            p.proposal_number or "",
            p.proposal_date.strftime("%d/%m/%Y") if p.proposal_date else "",
            f"{p.commission_value or 0:.2f}".replace(".", ","),
            p.status or "",
            p.operation_type or "",
            p.notes or "",
        ])

    data = "\ufeff" + output.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=propostas_consignado.csv"})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
