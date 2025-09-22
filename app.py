# Sajid Shaikh Algo Software : +91 9834370368

from fyers_apiv3 import fyersModel
from flask import Flask, request, render_template_string, jsonify, redirect
import webbrowser
import pandas as pd

# ---- Credentials ----
client_id = "VMS68P9EK0-100"
secret_key = "ZJ0CFWZEL1"
redirect_uri = "http://127.0.0.1:5000/callback"
grant_type = "authorization_code"
response_type = "code"
state = "sample"

# Step 1: Create session
appSession = fyersModel.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type=response_type,
    grant_type=grant_type,
    state=state
)

# Flask app
app = Flask(__name__)
app.secret_key = "sajid_secret"

access_token_global = None
fyers = None
atm_strike = None
initial_data = None  # Store initial LTP snapshot


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/login")
def login():
    login_url = appSession.generate_authcode()
    webbrowser.open(login_url, new=1)
    return redirect(login_url)


@app.route("/callback")
def callback():
    global access_token_global, fyers
    auth_code = request.args.get("auth_code")
    if auth_code:
        appSession.set_token(auth_code)
        token_response = appSession.generate_token()
        access_token_global = token_response.get("access_token")
        fyers = fyersModel.FyersModel(
            client_id=client_id,
            token=access_token_global,
            is_async=False,
            log_path=""
        )
        return "<h2>✅ Authentication Successful! You can return to the app 🚀</h2>"
    return "❌ Authentication failed. Please retry."


@app.route("/fetch")
def fetch_option_chain():
    global fyers, atm_strike, initial_data
    if fyers is None:
        return jsonify({"error": "⚠ Please login first!"})

    try:
        data = {"symbol": "NSE:NIFTY50-INDEX", "strikecount": 20, "timestamp": ""}
        response = fyers.optionchain(data=data)

        if "data" not in response or "optionsChain" not in response["data"]:
            return jsonify({"error": f"Invalid response from API: {response}"})

        options_data = response["data"]["optionsChain"]
        if not options_data:
            return jsonify({"error": "No options data found!"})

        df = pd.DataFrame(options_data)
        df_pivot = df.pivot_table(
            index="strike_price",
            columns="option_type",
            values="ltp",
            aggfunc="first"
        ).reset_index()
        df_pivot = df_pivot.rename(columns={"CE": "CE_LTP", "PE": "PE_LTP"})

        # ATM strike (fix only once)
        if atm_strike is None:
            nifty_spot = response["data"].get("underlyingValue", df_pivot["strike_price"].iloc[len(df_pivot)//2])
            atm_strike = min(df_pivot["strike_price"], key=lambda x: abs(x - nifty_spot))
            # Save initial snapshot for LTP
            initial_data = df_pivot.to_dict(orient="records")

        return df_pivot.to_json(orient="records")
    except Exception as e:
        return jsonify({"error": str(e)})


# ---------- HTML Template (inline) ----------
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Sajid Shaikh Algo Software</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f4f4f9; padding: 20px; }
    h2 { color: #1a73e8; }
    table { border-collapse: collapse; width: 70%; margin-top: 10px; }
    th, td { border: 1px solid #aaa; padding: 8px; text-align: center; }
    th { background-color: #1a73e8; color: white; }
    tr:nth-child(even) { background-color: #f2f2f2; }
    tr.atm { background-color: #ffeb3b; font-weight: bold; }
    tr.ce_special { background-color: #a8e6cf; font-weight: bold; }
    tr.pe_special { background-color: #ffaaa5; font-weight: bold; }
    a { text-decoration: none; padding: 8px 12px; background: #4caf50; color: white; border-radius: 4px; }
    a:hover { background: #45a049; }
    #specialStrikes { margin-top: 10px; font-weight: bold; }
    #signals { margin-top: 15px; font-weight: bold; color: red; }
  </style>
  <script>
    var atmStrike = null;
    var ceSpecial = null;
    var peSpecial = null;
    var initialLTP = {};
    var signals = [];

    async function fetchChain(){
        let res = await fetch("/fetch");
        let data = await res.json();
        let tbl = document.getElementById("chain");
        tbl.innerHTML = "";
        let specialDiv = document.getElementById("specialStrikes");
        let signalsDiv = document.getElementById("signals");

        if(data.error){
            tbl.innerHTML = `<tr><td colspan="3">${data.error}</td></tr>`;
            specialDiv.innerHTML = "";
            signalsDiv.innerHTML = "";
            return;
        }

        // Fix strikes only once
        if(atmStrike === null){
            atmStrike = data[Math.floor(data.length/2)].strike_price;
            ceSpecial = atmStrike - 300;
            peSpecial = atmStrike + 300;
        }

        // Save initial LTP snapshot only once
        if(Object.keys(initialLTP).length === 0){
            data.forEach(r => {
                initialLTP[r.strike_price] = {CE: r.CE_LTP, PE: r.PE_LTP};
            });
        }

        // Live LTP for special strikes
        let atmLive = data.find(r => r.strike_price === atmStrike);
        let ceLive = data.find(r => r.strike_price === ceSpecial);
        let peLive = data.find(r => r.strike_price === peSpecial);

        // Capture signals if Live LTP > LTP + 20
        if(atmLive?.CE_LTP > (initialLTP[atmStrike]?.CE + 20) || atmLive?.PE_LTP > (initialLTP[atmStrike]?.PE + 20)){
            if(!signals.includes("ATM Strike")) signals.push("ATM Strike");
        }
        if(ceLive?.CE_LTP > (initialLTP[ceSpecial]?.CE + 20)){
            if(!signals.includes("CE ATM-300")) signals.push("CE ATM-300");
        }
        if(peLive?.PE_LTP > (initialLTP[peSpecial]?.PE + 20)){
            if(!signals.includes("PE ATM+300")) signals.push("PE ATM+300");
        }

        // Display special strikes with LTP and Live
        specialDiv.innerHTML = `
            ATM Strike: ${atmStrike} (LTP: CE ${initialLTP[atmStrike]?.CE}, PE ${initialLTP[atmStrike]?.PE} | Live: CE ${atmLive?.CE_LTP}, PE ${atmLive?.PE_LTP}) <br>
            CE ATM-300: ${ceSpecial} (LTP: CE ${initialLTP[ceSpecial]?.CE} | Live: CE ${ceLive?.CE_LTP}) <br>
            PE ATM+300: ${peSpecial} (LTP: PE ${initialLTP[peSpecial]?.PE} | Live: PE ${peLive?.PE_LTP})
        `;

        // Display signals
        signalsDiv.innerHTML = signals.length > 0 ? "📢 Capture Signals: " + signals.join(", ") : "No signals";

        // Display full table
        data.forEach(row=>{
            let cls = "";
            let CE_display = row.CE_LTP;
            let PE_display = row.PE_LTP;

            if(row.strike_price === atmStrike){
                cls = "atm";
                CE_display = `${initialLTP[atmStrike]?.CE} / ${atmLive?.CE_LTP}`;
                PE_display = `${initialLTP[atmStrike]?.PE} / ${atmLive?.PE_LTP}`;
            } else if(row.strike_price === ceSpecial){
                cls = "ce_special";
                CE_display = `${initialLTP[ceSpecial]?.CE} / ${ceLive?.CE_LTP}`;
            } else if(row.strike_price === peSpecial){
                cls = "pe_special";
                PE_display = `${initialLTP[peSpecial]?.PE} / ${peLive?.PE_LTP}`;
            }

            tbl.innerHTML += `<tr class="${cls}"><td>${row.strike_price}</td><td>${CE_display}</td><td>${PE_display}</td></tr>`;
        });
    }

    setInterval(fetchChain, 2000);  // auto-refresh every 2 seconds
  </script>
</head>
<body>
  <h2>Sajid Shaikh Algo Software : +91 9834370368</h2>
  <a href="/login" target="_blank">🔑 Login</a>
  <div id="specialStrikes"></div>
  <div id="signals"></div>
  <h3>Option Chain</h3>
  <table>
    <thead><tr><th>Strike</th><th>CE LTP / Live</th><th>PE LTP / Live</th></tr></thead>
    <tbody id="chain"></tbody>
  </table>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(port=5000, debug=True)
