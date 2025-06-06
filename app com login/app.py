from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'GSSERS2025'

usuarios = {}
relatos = []

def reverse_geocode(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
    try:
        r = requests.get(url, headers={"User-Agent": "weather-app"})
        data = r.json()
        cidade = data.get("address", {}).get("city") or data.get("address", {}).get("town") or data.get("address", {}).get("village") or data.get("address", {}).get("state")
        return cidade
    except:
        return None

def geocode_city(cidade):
    url = f"https://nominatim.openstreetmap.org/search?format=jsonv2&q={cidade}"
    try:
        r = requests.get(url, headers={"User-Agent": "weather-app"})
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        return None, None
    except:
        return None, None

def buscar_previsao(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode&current_weather=true&timezone=auto"
    )
    try:
        r = requests.get(url)
        data = r.json()
        return data
    except:
        return None

def traduzir_tempo(codigo):
    mapa = {
        0: "Céu limpo",
        1: "Principalmente claro",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Neblina",
        48: "Orvalho congelante",
        51: "Chuva leve",
        53: "Chuva moderada",
        55: "Chuva forte",
        56: "Chuva congelante leve",
        57: "Chuva congelante forte",
        61: "Chuva fraca",
        63: "Chuva moderada",
        65: "Chuva forte",
        66: "Chuva congelante fraca",
        67: "Chuva congelante forte",
        71: "Neve leve",
        73: "Neve moderada",
        75: "Neve forte",
        77: "Granizo",
        80: "Chuva de pancadas leve",
        81: "Chuva de pancadas moderada",
        82: "Chuva de pancadas forte",
        85: "Neve de pancadas leve",
        86: "Neve de pancadas forte",
        95: "Tempestade com trovoadas",
        96: "Tempestade com trovoadas e granizo leve",
        99: "Tempestade com trovoadas e granizo forte",
    }
    return mapa.get(codigo, "Desconhecido")

def verificar_perigo(weathercode_diario):
    perigos = {55, 57, 65, 67, 75, 77, 82, 86, 95, 96, 99}
    for c in weathercode_diario:
        if c in perigos:
            return True
    return False

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    cidade = None
    aviso = None
    clima = None
    previsao = None
    lat = None
    lon = None

    if request.method == 'POST':
        cidade_form = request.form.get('cidade', '').strip()
        lat_form = request.form.get('lat', '').strip()
        lon_form = request.form.get('lon', '').strip()

        if cidade_form:
            lat, lon = geocode_city(cidade_form)
            if lat is None or lon is None:
                aviso = "Cidade não encontrada."
            else:
                cidade = cidade_form
        elif lat_form and lon_form:
            try:
                lat = float(lat_form)
                lon = float(lon_form)
                cidade = reverse_geocode(lat, lon) or "Local desconhecido"
            except Exception:
                aviso = "Coordenadas inválidas."
        else:
            aviso = "Informe uma cidade ou selecione um ponto no mapa."

        if lat is not None and lon is not None and not aviso:
            dados = buscar_previsao(lat, lon)
            if dados:
                clima = {
                    "min": dados["daily"]["temperature_2m_min"][0],
                    "max": dados["daily"]["temperature_2m_max"][0],
                    "descricao": traduzir_tempo(dados["daily"]["weathercode"][0])
                }
                previsao = []
                dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
                for i, dia_data in enumerate(dados["daily"]["time"]):
                    dt = datetime.fromisoformat(dia_data)
                    previsao.append({
                        "dia": dias_semana[dt.weekday()],
                        "min": dados["daily"]["temperature_2m_min"][i],
                        "max": dados["daily"]["temperature_2m_max"][i],
                        "descricao": traduzir_tempo(dados["daily"]["weathercode"][i])
                    })

                if verificar_perigo(dados["daily"]["weathercode"]):
                    aviso = "Atenção: condições climáticas perigosas previstas!"
            else:
                aviso = "Erro ao buscar previsão do tempo."

    return render_template('index.html', cidade=cidade, aviso=aviso, clima=clima,
                           previsao=previsao, lat=lat, lon=lon, relatos=relatos)

@app.route('/adicionar_relato', methods=['POST'])
def adicionar_relato():
    if 'usuario' not in session:
        return jsonify({"erro": "Login necessário"}), 401

    data = request.json
    lat = data.get('lat')
    lon = data.get('lon')
    tipo = data.get('tipo')
    descricao = data.get('descricao')

    if not all([lat, lon, tipo, descricao]):
        return jsonify({"erro": "Todos os campos são obrigatórios"}), 400

    cidade = reverse_geocode(lat, lon) or "Local desconhecido"

    relato = {
        "lat": lat,
        "lon": lon,
        "tipo": tipo,
        "descricao": descricao,
        "cidade": cidade,  # Inclui cidade no relato
        "usuario": session['usuario'],
        "data": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    relatos.append(relato)
    return jsonify({"sucesso": True})


@app.route('/reverse_geocode')
def api_reverse_geocode():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({"erro": "Parâmetros lat e lon necessários"}), 400
    cidade = reverse_geocode(lat, lon)
    if cidade:
        return jsonify({"cidade": cidade})
    else:
        return jsonify({"cidade": None})

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '').strip()
        if not usuario or not senha:
            return render_template('cadastro.html', erro="Preencha todos os campos")
        if usuario in usuarios:
            return render_template('cadastro.html', erro="Usuário já existe")
        usuarios[usuario] = generate_password_hash(senha)
        session['usuario'] = usuario
        return redirect(url_for('index'))
    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '').strip()
        if usuario in usuarios and check_password_hash(usuarios[usuario], senha):
            session['usuario'] = usuario
            return redirect(url_for('index'))
        return render_template('login.html', erro="Usuário ou senha inválidos")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
