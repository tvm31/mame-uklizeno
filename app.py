import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# Configuration
# Poznámka: Diakritiku v textech (háčky/čárky) raději dočasně vynecháme pro stabilitu
st.set_page_config(page_title="Mame uklizeno", layout="wide", page_icon="🏠")

# Connection
# Ruční oprava klíče ze Secrets
creds = dict(st.secrets["connections"]["gsheets"])
# Odstraníme případné mezery a opravíme zalomení řádků
raw_key = creds["private_key"]
cleaned_key = raw_key.replace("\\n", "\n").strip()
if "-----BEGIN PRIVATE KEY-----" not in cleaned_key:
    cleaned_key = f"-----BEGIN PRIVATE KEY-----\n{cleaned_key}\n-----END PRIVATE KEY-----"
creds["private_key"] = cleaned_key

# Připojení s opravenými údaji
conn = st.connection("gsheets", type=GSheetsConnection, **creds)

# Helper: Log action history
def log_action(old_log, action):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    new_entry = f"[{now}] {action}"
    if pd.isna(old_log) or old_log == "":
        return new_entry
    return f"{new_entry}\n{old_log}"

# --- AUTHENTICATION ---
with st.sidebar:
    st.title("Nastaveni")
    admin_mode = st.text_input("Admin heslo", type="password") == "mojeheslo123"
    if admin_mode:
        st.success("Jste v rezimu spravce")

st.title("🏠 Mame uklizeno")
st.markdown("---")

tab_names = ["Uklid schodiste", "Uklid snehu"]
tabs = st.tabs(tab_names)

for i, tab in enumerate(tabs):
    sheet_name = "Schodiste" if i == 0 else "Snih"
    with tab:
        # 1. READ DATA
        try:
            raw_df = conn.read(worksheet=sheet_name, ttl=0)
        except Exception as e:
                    st.error(f"Technicka chyba: {e}")
                    continue

        # 2. ADMIN: ADD NEW RECORD
        if admin_mode:
            with st.expander(f"Novy zaznam: {tab_names[i]}"):
                with st.form(f"form_add_{sheet_name}", clear_on_submit=True):
                    d_prov = st.date_input("Datum provedeni", value=None)
                    u_typ = None
                    if sheet_name == "Snih":
                        u_typ = st.selectbox("Typ udrzby", ["Bezna udrzba", "Ztizena udrzba"])
                    note = st.text_input("Poznamka")

                    if st.form_submit_button("Ulozit zaznam"):
                        final_date = d_prov if d_prov else datetime.now().date()
                        new_row = {
                            "ID": str(uuid.uuid4())[:8],
                            "Datum_Provedeni": final_date.isoformat(),
                            "Datum_Zapisu": datetime.now().date().isoformat(),
                            "Typ_Udrzby": u_typ,
                            "Poznamka": note,
                            "Historie_Zmen": log_action("", "Vytvoreno"),
                            "Smazano": "NE"
                        }
                        # Prevod na DataFrame a spojeni
                        new_row_df = pd.DataFrame([new_row])
                        updated_df = pd.concat([raw_df, new_row_df], ignore_index=True)
                        conn.update(worksheet=sheet_name, data=updated_df)
                        st.success("Ulozeno!")
                        st.rerun()

        # 3. DISPLAY & FILTERS
        st.subheader("Prehled provedenych praci")
        if not raw_df.empty:
            df_view = raw_df[raw_df["Smazano"] == "NE"].copy()
            if not df_view.empty:
                df_view["Datum_Provedeni"] = pd.to_datetime(df_view["Datum_Provedeni"])

                c1, c2 = st.columns([1, 2])
                with c1:
                    view = st.radio("Zobrazit:", ["Vse", "Tento mesic", "Tento rok"], horizontal=True, key=f"v_{sheet_name}")

                now = datetime.now()
                if view == "Tento mesic":
                    df_view = df_view[df_view["Datum_Provedeni"].dt.month == now.month]
                elif view == "Tento rok":
                    df_view = df_view[df_view["Datum_Provedeni"].dt.year == now.year]

                display_df = df_view.sort_values("Datum_Provedeni", ascending=False).copy()
                display_df["Datum_Provedeni"] = display_df["Datum_Provedeni"].dt.strftime('%d.%m.%Y')

                st.dataframe(display_df[["Datum_Provedeni", "Typ_Udrzby", "Poznamka", "ID"]],
                             use_container_width=True, hide_index=True)

                # 4. ADMIN: EDIT / DELETE
                if admin_mode:
                    with st.expander("Upravit / Smazat existujici zaznam"):
                        edit_id = st.selectbox("Vyberte ID zaznamu", df_view["ID"], key=f"sel_{sheet_name}")
                        curr_row = df_view[df_view["ID"] == edit_id].iloc[0]

                        with st.form(f"edit_form_{sheet_name}"):
                            new_note = st.text_input("Upravit poznamku", value=curr_row["Poznamka"])
                            col_b1, col_b2 = st.columns(2)

                            if col_b1.form_submit_button("Ulozit zmeny"):
                                raw_df.loc[raw_df["ID"] == edit_id, "Poznamka"] = new_note
                                raw_df.loc[raw_df["ID"] == edit_id, "Historie_Zmen"] = log_action(
                                    curr_row["Historie_Zmen"], f"Upravena poznamka na: {new_note}"
                                )
                                conn.update(worksheet=sheet_name, data=raw_df)
                                st.success("Upraveno!")
                                st.rerun()

                            if col_b2.form_submit_button("SMAZAT ZAZNAM"):
                                raw_df.loc[raw_df["ID"] == edit_id, "Smazano"] = "ANO"
                                raw_df.loc[raw_df["ID"] == edit_id, "Historie_Zmen"] = log_action(
                                    curr_row["Historie_Zmen"], "Zaznam smazan"
                                )
                                conn.update(worksheet=sheet_name, data=raw_df)
                                st.warning("Smazano!")
                                st.rerun()
            else:
                st.info("Zadne aktivni zaznamy k zobrazeni.")
        else:
            st.info("Tabulka je zatim prazdna.")



