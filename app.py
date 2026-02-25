import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import urllib.parse

# Configuration
st.set_page_config(page_title="Mame uklizeno", layout="wide", page_icon="🏠")

# ZDE VYPLŇ SVOU SKUTEČNOU ADRESU APLIKACE PRO QR KÓD:
APP_URL = "https://mame-uklizeno.streamlit.app" 

if "admin_mode" not in st.session_state:
    st.session_state.admin_mode = False

# 1. CONNECTION
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. LOAD DICTIONARY
try:
    dict_df = conn.read(worksheet="Slovnik", ttl=60)
    translations = {}
    for lang in ["CS", "EN"]:
        if lang in dict_df.columns:
            translations[lang] = dict_df.set_index("Klic")[lang].to_dict()
except Exception as e:
    st.error("Nepodarilo se nacist list 'Slovnik'.")
    st.stop()

def log_action(old_log, action):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    new_entry = f"[{now}] {action}"
    if pd.isna(old_log) or str(old_log).strip() == "": return new_entry
    return f"{new_entry}\n{old_log}"

# --- AUTHENTICATION & LANGUAGE ---
with st.sidebar:
    selected_lang = st.selectbox("Jazyk / Language", ["CS", "EN"])
    def _t(key, fallback=None):
        if pd.isna(key) or not isinstance(key, str) or key == "": return key
        val = translations.get(selected_lang, {}).get(key, key)
        return val if val != key else (fallback if fallback else key)

    st.title(_t("settings", "Nastavení"))
    if not st.session_state.admin_mode:
        with st.form("login_form"):
            pwd = st.text_input(_t("admin_pass", "Admin heslo"), type="password")
            if st.form_submit_button(_t("login_btn", "Přihlásit")):
                if pwd == "mojeheslo123":
                    st.session_state.admin_mode = True
                    st.rerun()
                else: st.error("Chybné heslo / Wrong password")
    else:
        st.success(_t("admin_ok", "Admin mode"))
        if st.button(_t("logout_btn", "Odhlásit")):
            st.session_state.admin_mode = False
            st.rerun()
    
    st.markdown("---")
    with st.expander(_t("share_app_title", "QR")):
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(_t('app_url', APP_URL))}&margin=10"
        st.image(qr_url)

# --- MAIN UI ---
st.title(f"🏠 {_t('app_title')}")

# --- MESSAGE BOARD (NÁSTĚNKA) ---
try:
    zpravy_df = conn.read(worksheet="Zpravy", ttl=0)
    if not zpravy_df.empty:
        aktivni = zpravy_df[zpravy_df["Smazano"] == "NE"]
        dnes = datetime.now().date()
        for _, z in aktivni.iterrows():
            zobrazit = True
            if pd.notna(z["Platnost_Do"]) and str(z["Platnost_Do"]).strip() != "":
                try:
                    if dnes > pd.to_datetime(z["Platnost_Do"]).date(): zobrazit = False
                except: pass
            if zobrazit:
                with st.chat_message("info"):
                    if pd.notna(z["Nadpis"]) and str(z["Nadpis"]).strip() != "":
                        st.markdown(f"**{z['Nadpis']}**")
                    st.write(z["Text_Zpravy"])

    if st.session_state.admin_mode:
        with st.expander("🛠️ " + _t("msg_board")):
            with st.form("add_msg"):
                n_title = st.text_input(_t("msg_title_label"))
                n_text = st.text_area(_t("msg_text"))
                n_valid = st.date_input(_t("msg_valid_until"), value=None)
                if st.form_submit_button(_t("save_btn")):
                    new_m = {"ID": str(uuid.uuid4())[:8], "Nadpis": n_title, "Text_Zpravy": n_text, "Platnost_Do": n_valid.isoformat() if n_valid else "", "Smazano": "NE"}
                    conn.update(worksheet="Zpravy", data=pd.concat([zpravy_df, pd.DataFrame([new_m])], ignore_index=True))
                    st.rerun()
except: pass

st.markdown("---")
tabs = st.tabs([_t("tab_stairs"), _t("tab_snow")])

for i, tab in enumerate(tabs):
    sheet_name = "Schodiste" if i == 0 else "Snih"
    with tab:
        try:
            raw_df = conn.read(worksheet=sheet_name, ttl=0)
        except: continue

        # DYNAMICKÝ STATUS (Semafor)
        if sheet_name == "Schodiste" and not raw_df.empty:
            clean_df = raw_df[raw_df["Smazano"] == "NE"]
            if not clean_df.empty:
                last_dt = pd.to_datetime(clean_df["Datum_Provedeni"]).max()
                diff = (datetime.now() - last_dt).days
                msg = f"{_t('status_last_clean')} {diff} {_t('status_days_count')}."
                if diff < 7: st.success(f"✅ {msg} {_t('status_clean_ok')}")
                elif diff <= 14: st.warning(f"⚠️ {msg} {_t('status_clean_warn')}")
                else: st.error(f"🚨 {msg} {_t('status_clean_err')}")

        # ADMIN: ADD RECORD
        if st.session_state.admin_mode:
            with st.expander(_t("new_record")):
                with st.form(f"add_{sheet_name}", clear_on_submit=True):
                    d_p = st.date_input(_t("date_done"), value=None)
                    u_t = st.selectbox(_t("maint_type"), ["Bezna udrzba", "Ztizena udrzba"], format_func=lambda x: _t(x)) if sheet_name == "Snih" else ""
                    nt = st.text_input(_t("note"))
                    if st.form_submit_button(_t("save_btn")):
                        row = {"ID": str(uuid.uuid4())[:8], "Datum_Provedeni": (d_p if d_p else datetime.now().date()).isoformat(), "Datum_Zapisu": datetime.now().date().isoformat(), "Typ_Udrzby": u_t, "Poznamka": nt, "Historie_Zmen": log_action("", "[[log_created]]"), "Smazano": "NE"}
                        conn.update(worksheet=sheet_name, data=pd.concat([raw_df, pd.DataFrame([row])], ignore_index=True))
                        st.rerun()

        # DISPLAY TABLE
        if not raw_df.empty:
            df_v = raw_df[raw_df["Smazano"] == "NE"].copy()
            if not df_v.empty:
                df_v["Datum_Provedeni"] = pd.to_datetime(df_v["Datum_Provedeni"])
                # Měsíční filtr
                m_list = [_t("show_all")] + [m.strftime('%m/%Y') for m in sorted(df_v["Datum_Provedeni"].dt.to_period('M').unique(), reverse=True)]
                sel_m = st.selectbox(_t("billing_month"), m_list, key=f"f_{sheet_name}")
                if sel_m != _t("show_all"):
                    df_v = df_v[df_v["Datum_Provedeni"].dt.strftime('%m/%Y') == sel_m]
                
                # Formátování pro zobrazení
                df_v = df_v.sort_values(by="Datum_Provedeni", ascending=False)
                df_v["Datum_Provedeni"] = df_v["Datum_Provedeni"].dt.strftime('%d.%m.%Y')
                df_v["Datum_Zapisu"] = pd.to_datetime(df_v["Datum_Zapisu"]).dt.strftime('%d.%m.%Y')
                
                # OŠETŘENÍ NONE v POZNÁMCE
                df_v["Poznamka"] = df_v["Poznamka"].apply(lambda x: "" if pd.isna(x) or str(x).lower() == "none" else x)
                
                if "Typ_Udrzby" in df_v.columns: df_v["Typ_Udrzby"] = df_v["Typ_Udrzby"].apply(lambda x: _t(x))
                
                def tr_log(s):
                    for tag in ["log_created", "log_edited", "log_deleted"]: s = str(s).replace(f"[[{tag}]]", _t(tag, tag))
                    return s
                df_v["Historie_Zmen"] = df_v["Historie_Zmen"].apply(tr_log)

                # Přejmenování a zobrazení
                ren = {"Datum_Provedeni": _t("col_date_done"), "Datum_Zapisu": _t("col_date_saved"), "Typ_Udrzby": _t("maint_type"), "Poznamka": _t("note"), "Historie_Zmen": _t("col_history"), "ID": "ID"}
                df_disp = df_v.rename(columns=ren)
                cols = [ren["Datum_Provedeni"]]
                if sheet_name == "Snih": cols.append(ren["Typ_Udrzby"])
                cols.extend([ren["Poznamka"], ren["Datum_Zapisu"], ren["Historie_Zmen"]])
                
                st.dataframe(df_disp[cols], use_container_width=True, hide_index=True)

                # ADMIN: EDIT
                if st.session_state.admin_mode:
                    with st.expander(_t("edit_expand")):
                        e_id = st.selectbox(_t("edit_select"), df_v["ID"], format_func=lambda x: f"{df_v[df_v['ID']==x].iloc[0]['Datum_Provedeni']} ({x})")
                        c_r = raw_df[raw_df["ID"] == e_id].iloc[0]
                        with st.form(f"ed_{e_id}"):
                            n_nt = st.text_input(_t("edit_note"), value=c_r["Poznamka"])
                            c1, c2 = st.columns(2)
                            if c1.form_submit_button(_t("save_changes")):
                                raw_df.loc[raw_df["ID"]==e_id, "Poznamka"] = n_nt
                                raw_df.loc[raw_df["ID"]==e_id, "Historie_Zmen"] = log_action(c_r["Historie_Zmen"], f"[[log_edited]] {n_nt}")
                                conn.update(worksheet=sheet_name, data=raw_df)
                                st.rerun()
                            if c2.form_submit_button(_t("del_btn")):
                                raw_df.loc[raw_df["ID"]==e_id, "Smazano"] = "ANO"
                                raw_df.loc[raw_df["ID"]==e_id, "Historie_Zmen"] = log_action(c_r["Historie_Zmen"], "[[log_deleted]]")
                                conn.update(worksheet=sheet_name, data=raw_df)
                                st.rerun()
