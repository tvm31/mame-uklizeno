import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import urllib.parse

# Configuration
st.set_page_config(page_title="Mame uklizeno", layout="wide", page_icon="🏠")

# Initialize session state for admin authentication
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
    st.error("Nepodarilo se nacist list 'Slovnik'. Zkontrolujte tabulku.")
    st.stop()

# Helper: Log action history
def log_action(old_log, action):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    new_entry = f"[{now}] {action}"
    if pd.isna(old_log) or str(old_log).strip() == "":
        return new_entry
    return f"{new_entry}\n{old_log}"

# --- AUTHENTICATION & LANGUAGE ---
with st.sidebar:
    selected_lang = st.selectbox("Jazyk / Language", ["CS", "EN"])
    
    # Helper translation function
    def _t(key, fallback=None):
        if pd.isna(key) or not isinstance(key, str) or key == "":
            return key
        val = translations.get(selected_lang, {}).get(key, key)
        return val if val != key else (fallback if fallback else key)

    st.title(_t("settings", "Nastavení"))
    
    # Handle persistent login state with a proper form/button for mobile
    if not st.session_state.admin_mode:
        with st.form("login_form"):
            pwd = st.text_input(_t("admin_pass", "Admin heslo"), type="password")
            if st.form_submit_button(_t("login_btn", "Přihlásit / Login")):
                if pwd == "mojeheslo123":
                    st.session_state.admin_mode = True
                    st.rerun()
                else:
                    st.error("Chybné heslo" if selected_lang == "CS" else "Wrong password")
    else:
        st.success(_t("admin_ok", "Jste v režimu správce"))
        if st.button(_t("logout_btn", "Odhlásit / Logout")):
            st.session_state.admin_mode = False
            st.rerun()
            
    # --- SHARE APP QR CODE ---
    st.markdown("---")
    with st.expander(_t("share_app_title", "Sdílet aplikaci (QR)")):
        # Dynamically fetch URL from the dictionary (with a fallback)
        app_url = _t("app_url", "https://mame-uklizeno.streamlit.app")
        
        # Generate QR code
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(app_url)}&margin=10"
        st.image(qr_url)
        st.caption(_t("share_app_text", "Naskenujte kód pro otevření této aplikace v mobilu."))

# --- MAIN UI ---
st.title(f"🏠 {_t('app_title')}")
st.markdown("---")

tab_names = [_t("tab_stairs"), _t("tab_snow")]
tabs = st.tabs(tab_names)

for i, tab in enumerate(tabs):
    sheet_name = "Schodiste" if i == 0 else "Snih"
    
    with tab:
        # READ DATA
        try:
            raw_df = conn.read(worksheet=sheet_name, ttl=0)
        except Exception as e:
            st.error("Chyba pri nacitani dat z tabulky.")
            continue

        # ADMIN: ADD NEW RECORD
        if st.session_state.admin_mode:
            with st.expander(f"{_t('new_record')} {tab_names[i]}"):
                with st.form(f"form_add_{sheet_name}", clear_on_submit=True):
                    d_prov = st.date_input(_t("date_done"), value=None)
                    u_typ = None
                    if sheet_name == "Snih":
                        typ_options = ["Bezna udrzba", "Ztizena udrzba"]
                        u_typ = st.selectbox(_t("maint_type"), typ_options, format_func=lambda x: _t(x))
                    
                    note = st.text_input(_t("note"))

                    if st.form_submit_button(_t("save_btn")):
                        final_date = d_prov if d_prov else datetime.now().date()
                        new_row = {
                            "ID": str(uuid.uuid4())[:8],
                            "Datum_Provedeni": final_date.isoformat(),
                            "Datum_Zapisu": datetime.now().date().isoformat(),
                            "Typ_Udrzby": u_typ if u_typ else "",
                            "Poznamka": note,
                            "Historie_Zmen": log_action("", "[[log_created]]"),
                            "Smazano": "NE"
                        }
                        new_row_df = pd.DataFrame([new_row])
                        updated_df = pd.concat([raw_df, new_row_df], ignore_index=True)
                        conn.update(worksheet=sheet_name, data=updated_df)
                        st.success(_t("saved_ok"))
                        st.rerun()

        # DISPLAY & FILTERS
        st.subheader(_t("overview", "Přehled provedených prací"))
        
        if not raw_df.empty:
            df_view = raw_df[raw_df["Smazano"] == "NE"].copy()
            
            if not df_view.empty:
                df_view["Datum_Provedeni"] = pd.to_datetime(df_view["Datum_Provedeni"])
                df_view["Datum_Zapisu"] = pd.to_datetime(df_view["Datum_Zapisu"])

                valid_dates = df_view["Datum_Provedeni"].dropna()
                if not valid_dates.empty:
                    temp_months = sorted(valid_dates.dt.to_period('M').unique(), reverse=True)
                    month_year_list = [m.strftime('%m/%Y') for m in temp_months]
                else:
                    month_year_list = []

                filter_options = [_t("show_all", "Zobrazit vše")] + month_year_list

                selected_month = st.selectbox(
                    _t("billing_month", "Fakturační měsíc:"), 
                    filter_options, 
                    key=f"filter_{sheet_name}"
                )

                if selected_month != _t("show_all", "Zobrazit vše"):
                    df_view = df_view[df_view["Datum_Provedeni"].dt.strftime('%m/%Y') == selected_month]

                if df_view.empty:
                    st.info(_t("no_records_month", "Pro tento měsíc nejsou žádné záznamy."))
                else:
                    display_df = df_view.sort_values(by=["Datum_Provedeni", "Datum_Zapisu"], ascending=[False, False]).copy()
                    
                    display_df["Datum_Provedeni"] = display_df["Datum_Provedeni"].dt.strftime('%d.%m.%Y')
                    display_df["Datum_Zapisu"] = display_df["Datum_Zapisu"].dt.strftime('%d.%m.%Y')

                    if "Typ_Udrzby" in display_df.columns:
                        display_df["Typ_Udrzby"] = display_df["Typ_Udrzby"].apply(lambda x: _t(x))

                    def translate_log(log_str):
                        if pd.isna(log_str) or not str(log_str).strip():
                            return log_str
                        text = str(log_str)
                        tags = ["log_created", "log_edited", "log_deleted"]
                        for tag in tags:
                            text = text.replace(f"[[{tag}]]", _t(tag, tag))
                        return text

                    display_df["Historie_Zmen"] = display_df["Historie_Zmen"].apply(translate_log)

                    rename_dict = {
                        "Datum_Provedeni": _t("col_date_done", "Datum provedení"),
                        "Datum_Zapisu": _t("col_date_saved", "Datum zápisu"),
                        "Typ_Udrzby": _t("maint_type", "Typ údržby"),
                        "Poznamka": _t("note", "Poznámka"),
                        "Historie_Zmen": _t("col_history", "Historie změn"),
                        "ID": _t("col_id", "ID Záznamu")
                    }
                    display_df = display_df.rename(columns=rename_dict)

                    if sheet_name == "Snih":
                        cols_to_show = [rename_dict["Datum_Provedeni"], rename_dict["Datum_Zapisu"], rename_dict["Typ_Udrzby"], rename_dict["Poznamka"], rename_dict["Historie_Zmen"], rename_dict["ID"]]
                    else:
                        cols_to_show = [rename_dict["Datum_Provedeni"], rename_dict["Datum_Zapisu"], rename_dict["Poznamka"], rename_dict["Historie_Zmen"], rename_dict["ID"]]

                    st.dataframe(display_df[cols_to_show], use_container_width=True, hide_index=True)

                    # ADMIN: EDIT / DELETE
                    if st.session_state.admin_mode:
                        with st.expander(_t("edit_expand", "Upravit / Smazat existující záznam")):
                            edit_id = st.selectbox(_t("edit_select", "Vyberte ID záznamu pro úpravu"), display_df[rename_dict["ID"]], key=f"sel_{sheet_name}")
                            curr_row = raw_df[raw_df["ID"] == edit_id].iloc[0]

                            with st.form(f"edit_form_{sheet_name}"):
                                new_note = st.text_input(_t("edit_note", "Upravit poznámku"), value=curr_row["Poznamka"])
                                col_b1, col_b2 = st.columns(2)

                                if col_b1.form_submit_button(_t("save_changes", "Uložit změny")):
                                    raw_df.loc[raw_df["ID"] == edit_id, "Poznamka"] = new_note
                                    raw_df.loc[raw_df["ID"] == edit_id, "Historie_Zmen"] = log_action(
                                        curr_row["Historie_Zmen"], f"[[log_edited]] {new_note}"
                                    )
                                    conn.update(worksheet=sheet_name, data=raw_df)
                                    st.success(_t("edited_ok", "Upraveno!"))
                                    st.rerun()

                                if col_b2.form_submit_button(_t("del_btn", "SMAZAT ZÁZNAM")):
                                    raw_df.loc[raw_df["ID"] == edit_id, "Smazano"] = "ANO"
                                    raw_df.loc[raw_df["ID"] == edit_id, "Historie_Zmen"] = log_action(
                                        curr_row["Historie_Zmen"], "[[log_deleted]]"
                                    )
                                    conn.update(worksheet=sheet_name, data=raw_df)
                                    st.warning(_t("deleted_ok", "Smazáno!"))
                                    st.rerun()
            else:
                st.info(_t("no_records_all", "Zatím nebyly provedeny žádné práce."))
        else:
            st.info(_t("empty_table", "Tabulka je zatím prázdná."))
