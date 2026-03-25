"""
deploy.py — Deploy automático para VPS Hostinger
Uso: python deploy.py
"""
import sys
import time

HOST = "148.230.79.134"
USER = "root"
PASS = "BrunoBronks@2025"
REPO = "https://github.com/bruno-bronks/bet.git"
APP_DIR = "/opt/bet"

ENV_CONTENT = r"""PROJECT_NAME="Football Probabilistic Analysis Platform"
VERSION="1.0.0"
DEBUG=false
BRASILEIRAO_NAME=brasileirao
UCL_NAME=champions_league
API_HOST=0.0.0.0
API_PORT=8000
API_PREFIX=/api/v1
DATABASE_URL=sqlite:///./football_analysis.db
RANDOM_STATE=42
TEST_SIZE=0.2
VALIDATION_SIZE=0.1
ROLLING_WINDOWS=[3,5,10]
RECENT_FORM_MATCHES=5
ELO_K_FACTOR=32.0
ELO_INITIAL_RATING=1500.0
ELO_HOME_ADVANTAGE=100.0
FOOTBALL_DATA_KEY=2e0fd7f5afd64a9d997eab014ef6cc84
FOOTBALL_DATA_BASE_URL=https://api.football-data.org/v4
API_FOOTBALL_KEY=677757d29a30bd0bf42a2e14bd43a17d
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
LOG_LEVEL=INFO
"""

NGINX_CONF = f"""server {{
    listen 8080;
    server_name _;

    # Frontend (React build)
    root {APP_DIR}/frontend/dist;
    index index.html;

    # API proxy -> uvicorn
    location /api/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }}

    location /health {{
        proxy_pass http://127.0.0.1:8000;
    }}

    location /docs {{
        proxy_pass http://127.0.0.1:8000;
    }}

    location /redoc {{
        proxy_pass http://127.0.0.1:8000;
    }}

    # SPA fallback
    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
"""

SYSTEMD_SERVICE = f"""[Unit]
Description=Football Analytics Backend (uvicorn)
After=network.target

[Service]
User=root
WorkingDirectory={APP_DIR}
Environment=PATH={APP_DIR}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart={APP_DIR}/venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

try:
    import paramiko
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run(ssh, cmd, desc="", timeout=120):
    print(f"  -> {desc or cmd[:60]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    rc = stdout.channel.recv_exit_status()
    if out:
        # Remove non-printable box-drawing chars
        safe = "".join(c if ord(c) < 0x2500 or ord(c) > 0x257F else "|" for c in out)
        print(f"    {safe[:400]}")
    if rc != 0 and err:
        safe_err = "".join(c if ord(c) < 0x2500 or ord(c) > 0x257F else "|" for c in err)
        print(f"    STDERR: {safe_err[:400]}")
    return rc, out, err


def write_file(sftp, path, content):
    with sftp.open(path, "w") as f:
        f.write(content)
    print(f"  -> Arquivo escrito: {path}")


def deploy():
    print(f"\n{'='*56}")
    print(f"  Deploy -> {HOST}")
    print(f"{'='*56}\n")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = ssh.open_sftp()
    print("  Conectado ao VPS\n")

    # ── 1. Sistema ────────────────────────────────────────────────────────────
    print("[1/7] Atualizando sistema e instalando dependencias...")
    run(ssh, "apt-get update -qq", "apt update", timeout=120)

    # Detectar versão do Python disponível
    rc, py_ver, _ = run(ssh, "python3 --version 2>&1", "detectar python")
    print(f"  -> Python disponivel: {py_ver}")

    run(ssh, "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip python3-venv git nginx curl build-essential", "instalar pacotes base", timeout=300)

    # Node.js — checar versao existente
    rc, _, _ = run(ssh, "node --version 2>/dev/null | grep -E 'v2[0-9]'", "checar node 20+")
    if rc != 0:
        print("  -> Instalando Node.js 22...")
        run(ssh, "curl -fsSL https://deb.nodesource.com/setup_22.x | bash - 2>/dev/null", "NodeSource setup", timeout=120)
        run(ssh, "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs", "instalar nodejs", timeout=120)

    run(ssh, "node --version && npm --version", "versoes node/npm")

    # ── 2. Clonar / atualizar repo ────────────────────────────────────────────
    print("\n[2/7] Clonando repositório...")
    rc, _, _ = run(ssh, f"test -d {APP_DIR}/.git", "checar repo existente")
    if rc == 0:
        run(ssh, f"cd {APP_DIR} && git pull --ff-only", "git pull", timeout=60)
    else:
        run(ssh, f"git clone {REPO} {APP_DIR}", "git clone", timeout=120)

    # ── 3. Configurar .env ────────────────────────────────────────────────────
    print("\n[3/7] Configurando .env...")
    write_file(sftp, f"{APP_DIR}/.env", ENV_CONTENT)

    # ── 4. Python venv + dependências ─────────────────────────────────────────
    print("\n[4/7] Configurando Python venv...")
    run(ssh, f"python3 -m venv {APP_DIR}/venv --clear", "criar venv")
    run(ssh, f"{APP_DIR}/venv/bin/pip install --upgrade pip -q", "upgrade pip", timeout=60)
    run(ssh, f"{APP_DIR}/venv/bin/pip install -r {APP_DIR}/requirements.txt -q", "instalar requirements", timeout=300)

    # ── 5. Frontend ───────────────────────────────────────────────────────────
    print("\n[5/7] Buildando frontend...")
    run(ssh, f"cd {APP_DIR}/frontend && npm install --silent 2>/dev/null", "npm install", timeout=300)
    run(ssh, f"cd {APP_DIR}/frontend && npm run build 2>&1 | tail -5", "npm run build", timeout=120)

    # ── 6. Nginx ──────────────────────────────────────────────────────────────
    print("\n[6/7] Configurando nginx...")
    write_file(sftp, "/etc/nginx/sites-available/bet", NGINX_CONF)
    run(ssh, "ln -sf /etc/nginx/sites-available/bet /etc/nginx/sites-enabled/bet", "link nginx config")
    # Remover todos os outros sites que possam conflitar (default, genoma, etc.)
    run(ssh, "find /etc/nginx/sites-enabled/ -type l ! -name 'bet' -delete", "remover outros sites")
    rc, out, _ = run(ssh, "nginx -t 2>&1", "testar config nginx")
    run(ssh, "systemctl stop nginx 2>/dev/null; true", "parar nginx")
    run(ssh, "systemctl start nginx", "iniciar nginx")
    run(ssh, "systemctl enable nginx", "enable nginx")

    # ── 7. Systemd service ────────────────────────────────────────────────────
    print("\n[7/7] Configurando serviço uvicorn...")
    write_file(sftp, "/etc/systemd/system/bet-backend.service", SYSTEMD_SERVICE)
    run(ssh, "systemctl daemon-reload", "daemon-reload")
    run(ssh, "systemctl enable bet-backend", "enable service")
    run(ssh, "systemctl restart bet-backend", "start backend")

    time.sleep(5)
    rc, out, _ = run(ssh, "systemctl is-active bet-backend", "status backend")
    print(f"\n  Backend status: {out}")

    if out != "active":
        rc2, log_out, _ = run(ssh, "journalctl -u bet-backend -n 20 --no-pager 2>&1", "logs backend", timeout=15)
        print(f"  Logs:\n    {log_out[:800]}")

    rc, out, _ = run(ssh, "curl -s --max-time 10 http://127.0.0.1:8000/health", "health check", timeout=20)
    print(f"  Health: {out[:200]}")

    rc, out, _ = run(ssh, "systemctl is-active nginx", "status nginx")
    print(f"  Nginx status: {out}")

    sftp.close()
    ssh.close()

    print(f"\n{'='*56}")
    print(f"  Deploy concluído!")
    print(f"  URL: http://{HOST}:8080")
    print(f"  API: http://{HOST}:8080/api/v1/")
    print(f"  Docs: http://{HOST}:8080/docs")
    print(f"{'='*56}\n")


if __name__ == "__main__":
    deploy()
