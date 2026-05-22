"""Componenti Streamlit riusabili per tutti i predictor."""
import streamlit as st
import pandas as pd
import numpy as np
from ..config import PredictorConfig
from ..prediction import predict_match, build_features_from_odds
from ..storage import (
    init_db, save_prediction, set_result, get_all_predictions, get_roi_stats,
    save_odds_cache, load_odds_cache, save_strategia_mista, get_strategia_mista,
    set_result_strategia, get_roi_strategia,
)
from ..scraper import get_upcoming_odds
from ..results_updater import auto_update_results

# Parametri strategia mista (calibrati su analisi storica)
N_SAFE = 9
N_JOLLY = 1
MIN_GAP = 0.15
MIN_Q_JOLLY = 5.0
ROI_ALERT_THRESHOLD = 0.08
SEASON_START = "2025-08-01"


def render_sidebar(cfg: PredictorConfig):
    """Sidebar con impostazioni comuni. Restituisce (use_mock, use_kelly, bankroll)."""
    with st.sidebar:
        st.header("Impostazioni")
        use_mock = st.toggle("Usa dati di esempio (no API key)", value=not bool(cfg.odds_api_key))
        use_kelly = st.toggle("Kelly criterion", value=False)
        bankroll = None
        if use_kelly:
            bankroll = st.number_input("Bankroll (€)", min_value=10, value=100, step=10)
        st.divider()
        st.subheader("Stato sistema")
        model_ok = (cfg.models_dir / "model.joblib").exists()
        data_ok  = (cfg.data_processed / "dataset.csv").exists()
        st.write("🟢 Modello" if model_ok else "🔴 Modello non trovato")
        st.write("🟢 Dataset" if data_ok else "🔴 Dataset non trovato")
        if data_ok:
            df_info = pd.read_csv(cfg.data_processed / "dataset.csv")
            st.write(f"📊 {len(df_info)} partite nel dataset")
    return use_mock, use_kelly, bankroll


def render_tab_predictions(cfg: PredictorConfig, use_mock: bool, use_kelly: bool, bankroll):
    """Tab 1: Predizioni giornata."""
    st.subheader(f"Prossima giornata — {cfg.name}")

    if not (cfg.models_dir / "model.joblib").exists():
        st.error("Modello non trovato. Esegui prima il training.")
        return

    cached_matches, cached_at = load_odds_cache(cfg)
    col_btn, col_warn = st.columns([1, 3])
    with col_btn:
        load_clicked = st.button("🔄 Carica quote", type="primary")
    with col_warn:
        if cached_at and not use_mock:
            from datetime import datetime, timezone
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(cached_at.replace(" ","T")+"+00:00")).total_seconds()/3600
            if age_h > 6:
                st.warning(f"⚠️ Quote vecchie ({int(age_h)}h fa)")
            else:
                st.caption(f"📦 Cache aggiornata {int(age_h*60)}min fa")

    if load_clicked:
        with st.spinner("Recupero quote..."):
            try:
                if use_mock:
                    from ..scraper import get_upcoming_odds as _get
                    matches = _get(cfg)  # fallback mock se API fallisce
                else:
                    matches = get_upcoming_odds(cfg)
                    save_odds_cache(cfg, matches)
                st.session_state[f"matches_{cfg.name}"] = matches
            except Exception as e:
                st.error(f"Errore: {e}")

    matches = st.session_state.get(f"matches_{cfg.name}", [])
    if not matches:
        st.info("Clicca 'Carica quote' per vedere le predizioni.")
        return

    results = []
    for m in matches:
        try:
            pred = predict_match(m["home_team"], m["away_team"], m["odds"], cfg)
            suffix = pred["prediction"]
            bk_odds = [v for k, v in m["odds"].items() if k.endswith(suffix) and v > 1]
            avg_odds = round(sum(bk_odds)/len(bk_odds), 2) if bk_odds else None
            save_prediction(cfg, m["home_team"], m["away_team"], pred["prediction"],
                            pred["probs"]["H"], pred["probs"]["D"], pred["probs"]["A"],
                            pred.get("value_bet", False), avg_odds,
                            m.get("commence_time","")[:10])
            kelly_stake = None
            if pred.get("value_bet") and avg_odds and avg_odds > 1 and use_kelly:
                p = pred["probs"][pred["prediction"]]; b = avg_odds - 1
                kelly_stake = round(max((p*b-(1-p))/b, 0) * bankroll, 2)
            row = {
                "Casa": m["home_team"], "Trasferta": m["away_team"],
                "Predizione": pred["prediction_label"],
                "P(Casa) %": f"{pred['probs']['H']*100:.1f}",
                "P(Pareggio) %": f"{pred['probs']['D']*100:.1f}",
                "P(Trasferta) %": f"{pred['probs']['A']*100:.1f}",
                "Confidenza %": f"{pred['confidence']*100:.1f}",
                "Value Bet": "✅" if pred.get("value_bet") else "",
                **({"Scommetti (€)": f"{kelly_stake:.2f}" if kelly_stake else ""} if use_kelly else {}),
            }
            results.append(row)
        except Exception as e:
            st.warning(f"{m['home_team']} vs {m['away_team']}: {e}")

    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        from datetime import datetime
        cfg.data_exports.mkdir(parents=True, exist_ok=True)
        fname = f"predizioni_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        csv_bytes = pd.DataFrame(results).to_csv(index=False).encode("utf-8")
        (cfg.data_exports / fname).write_bytes(csv_bytes)
        st.download_button("📥 Esporta CSV", data=csv_bytes, file_name=fname, mime="text/csv")


def render_tab_manual(cfg: PredictorConfig):
    """Tab 2: Inserimento manuale."""
    st.subheader("Inserisci quote manualmente")
    col1, col2 = st.columns(2)
    with col1:
        home = st.text_input("Squadra casa", "Home")
        away = st.text_input("Squadra trasferta", "Away")
    with col2:
        st.write("**Quote Bet365**")
        b365h = st.number_input("1 (casa)", min_value=1.01, value=2.10, step=0.05)
        b365d = st.number_input("X (pareggio)", min_value=1.01, value=3.40, step=0.05)
        b365a = st.number_input("2 (trasferta)", min_value=1.01, value=3.20, step=0.05)

    if st.button("🔮 Predici", type="primary"):
        odds = {"B365H": b365h, "B365D": b365d, "B365A": b365a}
        try:
            pred = predict_match(home, away, odds, cfg)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Predizione", pred["prediction_label"])
            c2.metric(f"P({home})", f"{pred['probs']['H']*100:.1f}%")
            c3.metric("P(Pareggio)", f"{pred['probs']['D']*100:.1f}%")
            c4.metric(f"P({away})", f"{pred['probs']['A']*100:.1f}%")
        except Exception as e:
            st.error(f"Errore: {e}")


def render_tab_update(cfg: PredictorConfig):
    """Tab 3: Aggiorna dataset e ri-addestra."""
    st.subheader("Aggiorna dataset e ri-addestra il modello")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Scarica nuovi dati storici"):
            with st.spinner("Download CSV..."):
                try:
                    from ..scraper import download_all
                    download_all(cfg)
                    st.success("Download completato")
                except Exception as e:
                    st.error(f"Errore: {e}")
    with col2:
        if st.button("🏋️ Ri-addestra modello"):
            with st.spinner("Training in corso..."):
                try:
                    from ..training import run as train_run
                    processed_path = cfg.data_processed / "dataset.csv"
                    if processed_path.exists():
                        processed_path.unlink()
                    train_run(cfg)
                    st.success("Modello aggiornato!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")


def render_tab_history(cfg: PredictorConfig):
    """Tab 4: Storico predizioni."""
    st.subheader("Storico predizioni")
    if st.button("🔄 Aggiorna risultati", type="primary"):
        with st.spinner("Cerco risultati nei CSV..."):
            r = auto_update_results(cfg)
        if r["updated"] == 0 and r["still_missing"] == 0:
            st.info("Nessuna predizione in attesa.")
        else:
            if r["updated"]: st.success(f"Aggiornati {r['updated']} risultati.")
            if r["still_missing"]: st.warning(f"{r['still_missing']} partite non ancora nei CSV.")
        st.rerun()

    rows = get_all_predictions(cfg)
    if not rows:
        st.info("Nessuna predizione salvata.")
        return

    df_hist = pd.DataFrame(rows)
    stats = get_roi_stats(cfg)
    if stats["n"] > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("Value bet con risultato", stats["n"])
        c2.metric("Win rate", f"{stats['win_rate']*100:.1f}%")
        c3.metric("ROI reale", f"{stats['roi']*100:.1f}%" if stats["roi"] is not None else "—")
        st.divider()

    pending = df_hist[df_hist["result"].isna()]
    if not pending.empty:
        sel = st.selectbox("Seleziona partita", options=pending["id"].tolist(),
                           format_func=lambda i: next(f"{r['home_team']} vs {r['away_team']} ({r['match_date'] or r['created_at']})" for r in rows if r["id"]==i))
        res = st.radio("Risultato reale", ["H","D","A"], horizontal=True)
        if st.button("💾 Salva risultato"):
            set_result(cfg, sel, res)
            st.success("Salvato!"); st.rerun()

    display_cols = ["match_date","home_team","away_team","prediction","prob_h","prob_d","prob_a","value_bet","avg_odds","result"]
    st.dataframe(df_hist[display_cols].rename(columns={
        "match_date":"Data","home_team":"Casa","away_team":"Trasferta",
        "prediction":"Pred","prob_h":"P(H)","prob_d":"P(D)","prob_a":"P(A)",
        "value_bet":"VB","avg_odds":"Quota","result":"Risultato",
    }), use_container_width=True, hide_index=True)


def render_tab_strategy(cfg: PredictorConfig, use_mock: bool):
    """Tab 5: Strategia Mista."""
    st.subheader(f"🎯 Strategia Mista — {N_SAFE} safe + {N_JOLLY} jolly")
    st.caption(f"Filtro gap ≥ {MIN_GAP:.0%} | Jolly quota > {MIN_Q_JOLLY} | Alert ROI > {ROI_ALERT_THRESHOLD:.0%}")

    stats_s   = get_roi_strategia(cfg, season_start=SEASON_START)
    stats_all = get_roi_strategia(cfg)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scommesse stagione", stats_s["n"])
    c2.metric("P&L stagione (€)", f"{stats_s['pl']:+.2f}" if stats_s["n"] else "—")
    roi_val = stats_s["roi"]
    c3.metric("ROI stagione", f"{roi_val*100:+.1f}%" if roi_val is not None else "—")
    c4.metric("Scommesse totali", stats_all["n"])

    if roi_val is not None and roi_val >= ROI_ALERT_THRESHOLD and stats_s["n"] >= 20:
        st.success(f"🔥 **STAGIONE CALDA** — ROI {roi_val*100:+.1f}% su {stats_s['n']} scommesse.")
    elif stats_s["n"] >= 20:
        st.info(f"📊 ROI {roi_val*100:+.1f}% — mercato efficiente.")
    else:
        st.info(f"📊 Dati insufficienti (servono ≥ 20 scommesse, hai {stats_s['n']}).")

    st.divider()
    st.subheader("Segnali prossima giornata")

    def _quota_media(odds, esito):
        vals = [v for k,v in odds.items() if k.endswith(esito) and v > 1]
        return round(sum(vals)/len(vals), 2) if vals else None

    def _prob_gap(probs):
        s = sorted(probs.values(), reverse=True)
        return s[0] - s[1]

    def _max_quota(odds):
        best_e, best_q = "H", 0.0
        for e in ["H","D","A"]:
            vals = [v for k,v in odds.items() if k.endswith(e) and v > 1]
            if vals and max(vals) > best_q:
                best_q = max(vals); best_e = e
        return best_e, best_q

    if st.button("🔄 Calcola segnali giornata", type="primary"):
        cached, _ = load_odds_cache(cfg)
        try:
            raw_matches = get_upcoming_odds(cfg) if not use_mock and not cached else (cached or [])
            if not use_mock and not cached:
                save_odds_cache(cfg, raw_matches)
        except Exception as e:
            st.error(f"Errore quote: {e}"); raw_matches = []

        enriched = []
        for m in raw_matches:
            odds = m["odds"]
            qh, qd, qa = _quota_media(odds,"H"), _quota_media(odds,"D"), _quota_media(odds,"A")
            if not all([qh,qd,qa]): continue
            raw_probs = {"H":1/qh,"D":1/qd,"A":1/qa}
            tot = sum(raw_probs.values())
            probs = {k:v/tot for k,v in raw_probs.items()}
            gap = _prob_gap(probs)
            best_e = max(probs, key=probs.get)
            jolly_e, jolly_q = _max_quota(odds)
            enriched.append({
                "home_team": m["home_team"], "away_team": m["away_team"],
                "match_date": m.get("commence_time","")[:10],
                "probs": probs, "gap": gap,
                "best_esito": best_e, "best_quota": _quota_media(odds, best_e),
                "jolly_esito": jolly_e, "jolly_quota": jolly_q,
            })

        pool_safe  = sorted([e for e in enriched if e["gap"] >= MIN_GAP],
                            key=lambda x: x["probs"][x["best_esito"]], reverse=True)[:N_SAFE]
        pool_jolly = sorted([e for e in enriched if e["jolly_quota"] >= MIN_Q_JOLLY],
                            key=lambda x: x["jolly_quota"], reverse=True)[:N_JOLLY]

        if pool_safe:
            st.write(f"**✅ {len(pool_safe)} scommesse SAFE:**")
            st.dataframe(pd.DataFrame([{
                "Casa": e["home_team"], "Trasferta": e["away_team"], "Esito": e["best_esito"],
                "Prob %": f"{e['probs'][e['best_esito']]*100:.1f}", "Gap %": f"{e['gap']*100:.1f}",
                "Quota": e["best_quota"],
            } for e in pool_safe]), use_container_width=True, hide_index=True)
        else:
            st.warning(f"Nessuna partita con gap ≥ {MIN_GAP:.0%}.")

        if pool_jolly:
            st.write(f"**🎲 {len(pool_jolly)} scommessa JOLLY:**")
            st.dataframe(pd.DataFrame([{
                "Casa": e["home_team"], "Trasferta": e["away_team"],
                "Esito jolly": e["jolly_esito"], "Quota jolly": e["jolly_quota"],
            } for e in pool_jolly]), use_container_width=True, hide_index=True)
        else:
            st.warning(f"Nessuna partita con quota jolly ≥ {MIN_Q_JOLLY}.")

        scommesse_db = [
            {"match_date": e["match_date"], "home_team": e["home_team"], "away_team": e["away_team"],
             "tipo": "safe", "esito": e["best_esito"], "quota": e["best_quota"], "prob_gap": e["gap"]}
            for e in pool_safe
        ] + [
            {"match_date": e["match_date"], "home_team": e["home_team"], "away_team": e["away_team"],
             "tipo": "jolly", "esito": e["jolly_esito"], "quota": e["jolly_quota"], "prob_gap": e["gap"]}
            for e in pool_jolly
        ]
        save_strategia_mista(cfg, scommesse_db)
        st.caption("💾 Scommesse salvate nel DB.")

    st.divider()
    st.subheader("Storico scommesse strategia mista")
    rows_sm = get_strategia_mista(cfg)
    if not rows_sm:
        st.info("Nessuna scommessa registrata.")
        return

    df_sm = pd.DataFrame(rows_sm)
    pending_sm = df_sm[df_sm["result"].isna()]
    if not pending_sm.empty:
        with st.expander("📝 Registra risultati reali"):
            sel_id = st.selectbox("Partita", options=pending_sm["id"].tolist(),
                                  format_func=lambda i: next(f"{r['home_team']} vs {r['away_team']} ({r['match_date']}) [{r['tipo']}]" for r in rows_sm if r["id"]==i))
            res_sm = st.radio("Risultato", ["H","D","A"], horizontal=True, key="res_sm")
            if st.button("💾 Salva", key="save_sm"):
                set_result_strategia(cfg, sel_id, res_sm)
                st.success("Salvato!"); st.rerun()

    st.dataframe(df_sm[["match_date","home_team","away_team","tipo","esito","quota","prob_gap","result"]].rename(columns={
        "match_date":"Data","home_team":"Casa","away_team":"Trasferta",
        "tipo":"Tipo","esito":"Esito","quota":"Quota","prob_gap":"Gap","result":"Risultato",
    }), use_container_width=True, hide_index=True)
