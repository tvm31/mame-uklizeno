import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# Configuration
st.set_page_config(page_title="Máme uklizeno", layout="wide", page_icon="")

# Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper: Log action history
def log_action(old_log, action):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    new_entry = f"[{now}] {action}"
    if pd.isna(old_log) or old_log == "":
        return new_entry
    return f"{new_entry}\n{old_log}"

# --- AUTHENTICATION ---
# Zm si heslo níže na své vlastní
with st.sidebar:
    st.title("Nastavení")
    admin_mode = st.password_input("Admin heslo", type="password") == "mojeheslo123"
    if admin_mode:
        st.success("Jste v režimu správce")

st.title(" Máme uklizeno")
st.markdown("---")

tab_names = [" Úklid schodišt", " Úklid snhu"]
tabs = st.tabs(tab_names)

for i, tab in enumerate(tabs):
    sheet_name = "Schodiste" if i == 0 else "Snih"
    with tab:
        # 1. READ DATA
        try:
            raw_df = conn.read(worksheet=sheet_name, ttl=0)
        except:
            st.error(f"Nepodailo se naíst list '{sheet_name}'. Zkontrolujte Google Tabulku.")
            continue

        # 2. ADMIN: ADD NEW RECORD
        if admin_mode:
            with st.expander(f" Nový záznam: {tab_names[i]}"):
                with st.form(f"form_add_{sheet_name}", clear_on_submit=True):
                    d_prov = st.date_input("Datum provedení (nechte prázdné pro dnešek)", value=None)
                    u_typ = None
                    if sheet_name == "Snih":
                        u_typ = st.selectbox("Typ údržby", ["Bžná údržba", "Ztížená údržba"])
                    note = st.text_input("Poznámka")

                    if st.form_submit_button("Uložit záznam"):
                        final_date = d_prov if d_prov else datetime.now().date()
                        new_row = {
                            "ID": str(uuid.uuid4())[:8],
                            "Datum_Provedeni": final_date.isoformat(),
                            "Datum_Zapisu": datetime.now().date().isoformat(),
                            "Typ_Udrzby": u_typ,
                            "Poznamka": note,
                            "Historie_Zmen": log_action("", "Vytvoeno"),
                            "Smazano": "NE"
                        }
                        updated_df = pd.concat([raw_df, pd.DataFrame([new_row])], ignore_index=True)
                        conn.update(worksheet=sheet_name, data=updated_df)
                        st.success("Uloženo!")
                        st.rerun()

        # 3. DISPLAY & FILTERS
        st.subheader("Pehled provedených prací")
        if not raw_df.empty:
            # Filter valid data
            df_view = raw_df[raw_df["Smazano"] == "NE"].copy()
            if not df_view.empty:
                df_view["Datum_Provedeni"] = pd.to_datetime(df_view["Datum_Provedeni"])

                # Filter UI
                c1, c2 = st.columns([1, 2])
                with c1:
                    view = st.radio("Zobrazit:", ["Vše", "Tento msíc", "Tento rok"], horizontal=True, key=f"v_{sheet_name}")

                now = datetime.now()
                if view == "Tento msíc":
                    df_view = df_view[df_view["Datum_Provedeni"].dt.month == now.month]
                elif view == "Tento rok":
                    df_view = df_view[df_view["Datum_Provedeni"].dt.year == now.year]

                # Format for display
                display_df = df_view.sort_values("Datum_Provedeni", ascending=False).copy()
                display_df["Datum_Provedeni"] = display_df["Datum_Provedeni"].dt.strftime('%d.%m.%Y')

                st.dataframe(display_df[["Datum_Provedeni", "Typ_Udrzby", "Poznamka", "ID"]],
                             use_container_width=True, hide_index=True)

                # 4. ADMIN: EDIT / DELETE
                if admin_mode:
                    with st.expander(" Upravit / Smazat existující záznam"):
                        edit_id = st.selectbox("Vyberte ID záznamu", df_view["ID"], key=f"sel_{sheet_name}")
                        curr_row = df_view[df_view["ID"] == edit_id].iloc[0]

                        with st.form(f"edit_form_{sheet_name}"):
                            new_note = st.text_input("Upravit poznámku", value=curr_row["Poznamka"])
                            col_b1, col_b2 = st.columns(2)

                            if col_b1.form_submit_button("Uložit zmny"):
                                raw_df.loc[raw_df["ID"] == edit_id, "Poznamka"] = new_note
                                raw_df.loc[raw_df["ID"] == edit_id, "Historie_Zmen"] = log_action(
                                    curr_row["Historie_Zmen"], f"Upravena poznámka na: {new_note}"
                                )
                                conn.update(worksheet=sheet_name, data=raw_df)
                                st.success("Upraveno!")
                                st.rerun()

                            if col_b2.form_submit_button(" SMAZAT ZÁZNAM"):
                                raw_df.loc[raw_df["ID"] == edit_id, "Smazano"] = "ANO"
                                raw_df.loc[raw_df["ID"] == edit_id, "Historie_Zmen"] = log_action(
                                    curr_row["Historie_Zmen"], "Záznam smazán (soft-delete)"
                                )
                                conn.update(worksheet=sheet_name, data=raw_df)
                                st.warning("Smazáno!")
                                st.rerun()
            else:
                st.info("Žádné aktivní záznamy k zobrazení.")
        else:
            st.info("Tabulka je zatím prázdná.")