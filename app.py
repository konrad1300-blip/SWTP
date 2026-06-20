# -*- coding: utf-8 -*-
"""
app.py - Główny plik aplikacji webowej SWTP (System Wycen Technologii i Planowania) w Streamlit.
Wspomaga wyceny, technologię, dokumentację, planowanie produkcji (APS) i realizację w LAN.
Wszystkie komentarze i interfejs użytkownika są w języku polskim.
"""

import streamlit as st
import database
import scheduler
from datetime import datetime, date, time, timedelta
import pandas as pd
import json
import os

# Konfiguracja strony Streamlit
st.set_page_config(
    page_title="SWTP - System Wycen i Planowania",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Wstrzyknięcie stylów CSS dla unikalnego, nowoczesnego wyglądu (Aesthetics)
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        * {
            font-family: 'Outfit', sans-serif;
        }
        
        .main-header {
            font-size: 2.2rem;
            font-weight: 800;
            color: #1E3A8A;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .sub-header {
            font-size: 1.1rem;
            color: #6B7280;
            margin-bottom: 2rem;
        }
        
        .premium-card {
            background-color: #F8FAFC;
            border-left: 5px solid #3B82F6;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05);
            margin-bottom: 1.5rem;
        }
        
        .role-badge {
            background-color: #DBEAFE;
            color: #1E40AF;
            font-weight: 600;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            display: inline-block;
            margin-top: 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# Inicjalizacja baze danych
database.inicjalizuj_baze()

# Zmienne w stanie sesji (Session State)
if 'zalogowany' not in st.session_state:
    st.session_state['zalogowany'] = False
if 'uzytkownik' not in st.session_state:
    st.session_state['uzytkownik'] = None
if 'rola' not in st.session_state:
    st.session_state['rola'] = None
if 'awarie_symulacja' not in st.session_state:
    st.session_state['awarie_symulacja'] = {}

# --- PANEL LOGOWANIA ---
def ekran_logowania():
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏭 System SWTP</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Zaloguj się do firmowego portalu planowania produkcji (LAN)</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("formularz_logowania"):
            st.markdown("### Logowanie")
            login = st.text_input("Nazwa użytkownika")
            haslo = st.text_input("Hasło", type="password")
            zatwierdz = st.form_submit_button("Zaloguj się")
            
            if zatwierdz:
                rola = database.loguj_uzytkownika(login, haslo)
                if rola:
                    st.session_state['zalogowany'] = True
                    st.session_state['uzytkownik'] = login
                    st.session_state['rola'] = rola
                    st.success(f"Zalogowano pomyślnie jako {login} ({rola})")
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło.")
                    
        st.info("Konta demonstracyjne:\n- admin / admin (Menedżer)\n- planista / planista (Planista)\n- konstruktor / konstruktor (Konstruktor)\n- operator / operator (Operator)")

# --- PANEL BOCZNY (SIDEBAR) ---
def panel_boczny():
    with st.sidebar:
        st.markdown("### 🏢 Profil użytkownika")
        st.write(f"Zalogowany: **{st.session_state['uzytkownik']}**")
        st.markdown(f"<span class='role-badge'>{st.session_state['rola']}</span>", unsafe_allow_html=True)
        st.write("---")
        
        # Nawigacja w zależności od roli
        rola = st.session_state['rola']
        opcje = ["Harmonogram i Zadania", "Wycena i Karta Produktu", "Technologia", "Dokumentacja", "Wizualizacja APS (Gantt)", "Realizacja (Stanowisko LAN)", "Raporty Walidacji"]
        if rola == 'Menedżer':
            opcje.append("Zarządzanie Użytkownikami")
        
        wybor = st.radio("Menu Główne", opcje)
        st.write("---")
        
        # Opcje administratora / menedżera
        if rola == 'Menedżer':
            st.markdown("### ⚙️ Administracja")
            if st.button("Importuj dane z Excela"):
                with st.spinner("Importowanie danych... Może to zająć do 30 sekund."):
                    komunikat_container = st.empty()
                    def log_status(status_str):
                        komunikat_container.text(status_str)
                    database.importuj_dane_excel(status_callback=log_status)
                    st.success("Baza danych zaktualizowana plikami Excel!")
            st.write("---")
            
        if st.button("Wyloguj się", key="logout_btn"):
            st.session_state['zalogowany'] = False
            st.session_state['uzytkownik'] = None
            st.session_state['rola'] = None
            st.rerun()
            
    return wybor

# --- MODUŁ 1: HARMONOGRAM I ZADANIA ---
def modul_harmonogram():
    st.markdown("<h2 class='main-header'>📅 Harmonogram i Lista Zadań</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Zarządzanie zapytaniami od klientów, zamówieniami z Danii i priorytetami.</p>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Dodaj Nowe Zamówienie", "Kolejkowanie i Edycja Zamówień"])
    
    with tab1:
        st.subheader("Nowe zapytanie ofertowe / zlecenie")
        with st.form("nowe_zlecenie_form"):
            col1, col2 = st.columns(2)
            with col1:
                nr_zamowienia = st.text_input("Numer Zamówienia (np. ZAM-2026-001)")
                klient = st.text_input("Nazwa Klienta / Oddział")
                kod_produktu = st.text_input("Kod Produktu (np. 066-0120-001)")
            with col2:
                ilosc = st.number_input("Ilość (szt.)", min_value=1, value=10)
                termin = st.date_input("Termin Realizacji", value=date.today() + timedelta(days=7))
                priorytet = st.slider("Priorytet (1-najwyższy, 10-najniższy)", 1, 10, 1)
                
            submit = st.form_submit_button("Wprowadź do systemu")
            if submit:
                if not nr_zamowienia or not kod_produktu:
                    st.error("Numer zamówienia i kod produktu są wymagane.")
                else:
                    success = database.dodaj_zamowienie(nr_zamowienia, klient, kod_produktu, ilosc, termin.strftime('%Y-%m-%d'), priorytet)
                    if success:
                        st.success(f"Dodano zlecenie {nr_zamowienia} do bazy. Status: Do Wyceny / Wycenione.")
                    else:
                        st.error("Zlecenie o tym numerze już istnieje w systemie.")
                        
    with tab2:
        st.subheader("Bieżące zlecenia produkcyjne")
        st.info("💡 Możesz edytować statusy, priorytety i terminy bezpośrednio w tabeli poniżej. Zapisz zmiany po zakończeniu edycji.")
        
        zamowienia_rows = database.pobierz_zamowienia()
        if not zamowienia_rows:
            st.warning("Brak zamówień w systemie.")
        else:
            # Konwersja do DataFrame do edycji
            df_zam = pd.DataFrame([dict(r) for r in zamowienia_rows])
            df_zam['termin'] = pd.to_datetime(df_zam['termin']).dt.date
            
            # Edytor tabeli w Streamlit
            edytowany_df = st.data_editor(
                df_zam,
                column_config={
                    "id": None, # ukryj ID
                    "nr_zamowienia": st.column_config.TextColumn("Nr Zamówienia", disabled=True),
                    "klient": "Klient",
                    "kod_produktu": "Kod Produktu",
                    "ilosc": st.column_config.NumberColumn("Ilość", min_value=1),
                    "termin": st.column_config.DateColumn("Termin"),
                    "priorytet": st.column_config.NumberColumn("Priorytet (Kolejność)", min_value=1),
                    "status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["Harmonogram", "Do Wyceny", "Wycenione", "W Produkcji", "Zakończone"]
                    ),
                    "start_planowany": None,
                    "stop_planowany": None
                },
                num_rows="dynamic"
            )
            
            if st.button("Zapisz Zmiany w Harmonogramie"):
                conn = database.get_connection()
                cursor = conn.cursor()
                try:
                    for _, row in edytowany_df.iterrows():
                        # Konwersja daty do stringa
                        t_str = row['termin']
                        if isinstance(t_str, date):
                            t_str = t_str.strftime('%Y-%m-%d')
                            
                        cursor.execute("""
                        UPDATE zamowienia SET 
                            klient = ?, kod_produktu = ?, ilosc = ?, termin = ?, priorytet = ?, status = ?
                        WHERE id = ?
                        """, (row['klient'], row['kod_produktu'], row['ilosc'], t_str, row['priorytet'], row['status'], row['id']))
                    conn.commit()
                    st.success("Zapisano zmiany w bazie danych!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Błąd zapisu: {e}")
                finally:
                    conn.close()

# --- MODUŁ 2: WYCENA I KARTA PRODUKTU ---
def modul_wycena():
    st.markdown("<h2 class='main-header'>💰 Wycena i BOM Produktu</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Kalkulacja kosztów materiałowych (BOM) i robocizny maszynowej.</p>", unsafe_allow_html=True)
    
    # Wybór lub wpisanie produktu
    st.subheader("Identyfikacja Produktu")
    kod_produktu = st.text_input("Wpisz kod produktu (np. 066-0120-001 lub stwórz nowy)", value="").strip()
    
    if not kod_produktu:
        st.info("Wprowadź kod produktu w formacie maski (np. xxx-xxxx-xxx) aby rozpocząć wycenę.")
        return
        
    karta = database.pobierz_karte_produktu(kod_produktu)
    
    # Przycisk wczytywania BOM z ERP, jeśli produkt istnieje w seeded recepturach
    receptura_erp = database.pobierz_recepture_seeding(kod_produktu)
    
    if receptura_erp and not karta:
        st.info(f"💡 Znaleziono domyślną recepturę dla tego produktu w bazie ERP ({len(receptura_erp)} pozycji).")
        
    # Formularz karty produktu
    st.markdown("### Karta Techniczno-Wycenowa")
    nazwa_produktu = st.text_input("Nazwa Produktu", value=karta['nazwa'] if karta else (receptura_erp[0]['nazwa'] if receptura_erp else ""))
    
    col1, col2 = st.columns(2)
    with col1:
        plik_kroju = st.text_input("Ścieżka do pliku kroju (IA) / model", value=karta['plik_kroju'] if karta else "")
        metry_szycia = st.number_input("Metry Szycia (m)", min_value=0.0, value=karta['metry_szycia'] if karta else 0.0)
    with col2:
        metry_zgrzewania = st.number_input("Metry Zgrzewania (m)", min_value=0.0, value=karta['metry_zgrzewania'] if karta else 0.0)
        pasy_info = st.text_area("Informacje o pasach (długości, ilości)", value=karta['pasy_info'] if karta else "")
        
    inne_info = st.text_area("Dodatkowe informacje / uwagi", value=karta['inne_informacje'] if karta else "")

    st.write("---")
    
    # --- EDYCJA BOM (ZESTAWIENIE MATERIAŁOWE) ---
    st.markdown("### 🛒 Zestawienie Materiałowe (BOM)")
    
    # Inicjalizacja listy BOM w stanie sesji dla interaktywności
    if 'current_bom' not in st.session_state or st.session_state.get('bom_product_code') != kod_produktu:
        st.session_state['bom_product_code'] = kod_produktu
        if karta:
            # Wczytaj zapisany BOM
            st.session_state['current_bom'] = [
                {'kod_materialu': r['kod_materialu'], 'nazwa': r['nazwa'], 'typ_zasobu': r['typ_zasobu'], 'ilosc': r['ilosc'], 'cena': r['cena']}
                for r in database.pobierz_bom_produktu(kod_produktu)
            ]
        elif receptura_erp:
            # Wczytaj z ERP
            st.session_state['current_bom'] = [
                {'kod_materialu': r['kod_materialu'], 'nazwa': r['nazwa'], 'typ_zasobu': r['typ_zasobu'], 'ilosc': r['ilosc'], 'cena': r['cena']}
                for r in receptura_erp
            ]
        else:
            st.session_state['current_bom'] = []
            
    # Wyszukiwarka materiałów w bazie
    szukaj_mat = st.text_input("🔍 Wyszukaj i dodaj materiał do BOM (wpisz nazwę lub kod)")
    if szukaj_mat:
        wyniki = database.szukaj_materialów(szukaj_mat, limit=5)
        if wyniki:
            st.write("Znalezione materiały:")
            for w in wyniki:
                col_mat_btn, col_mat_cena = st.columns([3, 1])
                with col_mat_btn:
                    if st.button(f"Dodaj: {w['kod']} - {w['nazwa']} ({w['typ_zasobu']})", key=f"add_m_{w['kod']}"):
                        # Sprawdź czy już nie ma go na liście
                        if not any(x['kod_materialu'] == w['kod'] for x in st.session_state['current_bom']):
                            st.session_state['current_bom'].append({
                                'kod_materialu': w['kod'],
                                'nazwa': w['nazwa'],
                                'typ_zasobu': w['typ_zasobu'],
                                'ilosc': 1.0,
                                'cena': w['cena']
                            })
                            st.rerun()
                with col_mat_cena:
                    # Możliwość edycji ceny towaru bezpośrednio
                    nowa_cena_val = st.number_input("Cena", min_value=0.0, value=w['cena'], key=f"price_m_{w['kod']}")
                    if nowa_cena_val != w['cena']:
                        database.aktualizuj_cene_materialu(w['kod'], nowa_cena_val)
                        # Aktualizuj w bieżącym widoku
                        for item in st.session_state['current_bom']:
                            if item['kod_materialu'] == w['kod']:
                                item['cena'] = nowa_cena_val
                        st.success(f"Zaktualizowano cenę dla {w['kod']}")
                        st.rerun()

    # Wyświetlanie aktualnej listy BOM
    if st.session_state['current_bom']:
        df_bom_view = pd.DataFrame(st.session_state['current_bom'])
        st.markdown("**Bieżące pozycje w BOM:**")
        
        # Edycja ilości w tabeli
        for idx, row in df_bom_view.iterrows():
            col_k, col_n, col_i, col_c, col_suma, col_del = st.columns([2, 4, 1.5, 1.5, 1.5, 1])
            with col_k:
                st.text(row['kod_materialu'])
            with col_n:
                st.text(row['nazwa'])
            with col_i:
                nowa_ilosc = st.number_input("Ilość", min_value=0.0001, value=float(row['ilosc']), step=0.1, key=f"bom_qty_{idx}")
                st.session_state['current_bom'][idx]['ilosc'] = nowa_ilosc
            with col_c:
                st.text(f"{row['cena']:.2f} PLN")
            with col_suma:
                st.text(f"{row['cena'] * nowa_ilosc:.2f} PLN")
            with col_del:
                if st.button("❌", key=f"bom_del_{idx}"):
                    st.session_state['current_bom'].pop(idx)
                    st.rerun()
    else:
        st.warning("BOM jest pusty. Wyszukaj i dodaj materiały powyżej.")

    st.write("---")
    
    # --- PRZYPORZĄDKOWANIE PROCESÓW PRODUKCYJNYCH ---
    st.markdown("### ⚙️ Procesy Produkcyjne (Robocizna)")
    
    # Inicjalizacja procesów w sesji
    if 'current_procesy' not in st.session_state or st.session_state.get('proc_product_code') != kod_produktu:
        st.session_state['proc_product_code'] = kod_produktu
        if karta:
            st.session_state['current_procesy'] = [
                {'maszyna_id': r['maszyna_id'], 'maszyna_nazwa': r['maszyna_nazwa'], 'proces': r['proces'], 'czas_standardowy': r['czas_standardowy'], 'korekta_gabaryt': r['korekta_gabaryt']}
                for r in database.pobierz_procesy_wyceny_produktu(kod_produktu)
            ]
        else:
            st.session_state['current_procesy'] = []
            
    # Formularz dodawania procesów
    maszyny_lista = database.pobierz_maszyny()
    if maszyny_lista:
        maszyny_dict = {m['nazwa']: m for m in maszyny_lista}
        
        col_m, col_p, col_t, col_k, col_add_proc = st.columns([3, 3, 2, 2, 1])
        with col_m:
            wybrana_maszyna = st.selectbox("Wybierz Maszynę", list(maszyny_dict.keys()))
        with col_p:
            m_id = maszyny_dict[wybrana_maszyna]['id']
            lista_proc_maszyny = [p['proces'] for p in database.pobierz_procesy_maszyny(m_id)]
            if not lista_proc_maszyny:
                lista_proc_maszyny = ["Szycie", "Krojenie", "Zgrzewanie HF", "Pakowanie"]
            wybrany_proc = st.selectbox("Proces", lista_proc_maszyny)
        with col_t:
            czas_std = st.number_input("Czas std (h/szt)", min_value=0.001, value=0.1, step=0.05)
        with col_k:
            korekta = st.number_input("Modyfikator gabarytu", min_value=0.5, max_value=5.0, value=1.0, step=0.1)
        with col_add_proc:
            st.write("")
            st.write("")
            if st.button("➕"):
                st.session_state['current_procesy'].append({
                    'maszyna_id': m_id,
                    'maszyna_nazwa': wybrana_maszyna,
                    'proces': wybrany_proc,
                    'czas_standardowy': czas_std,
                    'korekta_gabaryt': korekta
                })
                st.rerun()
    else:
        st.error("Brak maszyn w bazie danych. Menedżer musi zaimportować bazę Excel.")

    # Wyświetlanie listy procesów
    if st.session_state['current_procesy']:
        st.markdown("**Wybrane procesy robocze:**")
        for idx, p in enumerate(st.session_state['current_procesy']):
            col_m_n, col_p_n, col_t_n, col_k_n, col_c_n, col_del_n = st.columns([3, 3, 2, 2, 2, 1])
            with col_m_n:
                st.text(p['maszyna_nazwa'])
            with col_p_n:
                st.text(p['proces'])
            with col_t_n:
                st.text(f"Czas: {p['czas_standardowy']:.3f} h")
            with col_k_n:
                st.text(f"Modyf: x{p['korekta_gabaryt']:.1f}")
            with col_c_n:
                # Wyciągnij stawkę maszynową
                stawki = database.pobierz_procesy_maszyny(p['maszyna_id'])
                stawka = 100.0 # Domyślnie
                for st_r in stawki:
                    if st_r['proces'] == p['proces']:
                        stawka = st_r['koszt_godzina']
                        break
                koszt_jedn = p['czas_standardowy'] * p['korekta_gabaryt'] * stawka
                st.text(f"{koszt_jedn:.2f} PLN/szt.")
            with col_del_n:
                if st.button("❌", key=f"proc_del_{idx}"):
                    st.session_state['current_procesy'].pop(idx)
                    st.rerun()
                    
    # Sumaryczne wyliczenia
    suma_bom = sum(item['ilosc'] * item['cena'] for item in st.session_state['current_bom'])
    
    suma_robocizna = 0.0
    for p in st.session_state['current_procesy']:
        stawki = database.pobierz_procesy_maszyny(p['maszyna_id'])
        stawka = 100.0
        for st_r in stawki:
            if st_r['proces'] == p['proces']:
                stawka = st_r['koszt_godzina']
                break
        suma_robocizna += p['czas_standardowy'] * p['korekta_gabaryt'] * stawka
        
    laczny_koszt = suma_bom + suma_robocizna
    
    st.write("---")
    st.markdown("### 📊 Podsumowanie Kalkulacji Kosztów")
    
    c_b1, c_b2, c_b3 = st.columns(3)
    c_b1.metric("Koszty materiałów (BOM)", f"{suma_bom:.2f} PLN")
    c_b2.metric("Koszty robocizny (czas pracy)", f"{suma_robocizna:.2f} PLN")
    c_b3.metric("Łączny koszt na 1 szt.", f"{laczny_koszt:.2f} PLN", delta=None)
    
    st.write("---")
    
    if st.button("ZAPISZ WYCENĘ I KARTĘ PRODUKTU"):
        if not nazwa_produktu:
            st.error("Musisz podać nazwę produktu.")
        else:
            success = database.stworz_karte_produktu_i_wycene(
                kod_produktu,
                nazwa_produktu,
                plik_kroju,
                metry_szycia,
                metry_zgrzewania,
                pasy_info,
                inne_info,
                st.session_state['current_bom'],
                st.session_state['current_procesy']
            )
            if success:
                st.success(f"Pomyślnie zapisano wycenę dla produktu: {kod_produktu}!")
                st.rerun()
            else:
                st.error("Błąd bazy danych podczas zapisu wyceny.")

# --- MODUŁ 3: TECHNOLOGIA ---
def modul_technologia():
    st.markdown("<h2 class='main-header'>⛓️ Karta Technologiczna (ERP)</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Powiązanie i złożenie procesów wyceny w sekwencję technologiczną.</p>", unsafe_allow_html=True)
    
    kod_produktu = st.text_input("Kod produktu do ułożenia technologii", value="").strip()
    
    if not kod_produktu:
        st.info("Podaj kod wycenionego produktu, aby otworzyć kartę technologiczną.")
        return
        
    karta = database.pobierz_karte_produktu(kod_produktu)
    if not karta:
        st.error("Brak wycenionego produktu o tym kodzie. Najpierw utwórz wycenę.")
        return
        
    st.write(f"Produkt: **{karta['nazwa']}** ({kod_produktu})")
    
    # Pobieramy procesy z wyceny
    procesy_wyceny = database.pobierz_procesy_wyceny_produktu(kod_produktu)
    if not procesy_wyceny:
        st.warning("Produkt nie posiada zdefiniowanych procesów roboczych w wycenie.")
        return
        
    st.markdown("### 1. Złożenie procesów z wyceny w sekwencję")
    st.write("Poniżej znajdują się zdefiniowane procesy. Przyporządkuj je do kroków technologicznych:")
    
    sekwencja_zapissana = database.pobierz_sekwencje_technologiczna(kod_produktu)
    
    # Grupy procesów z założeń: Krojenie, Nadruk, Elementy, Szycie, Zgrzewanie HF mały, Zgrzewanie HF duży, Zgrzewanie SEAMTEC, Zgrzewanie gorące powietrze, Okucia, Kontrola, Pakowanie
    kategorie_procesow = [
        "Krojenie", "Nadruk", "Elementy", "Szycie", "Zgrzewanie HF mały", 
        "Zgrzewanie HF duży", "Zgrzewanie SEAMTEC", "Zgrzewanie gorące powietrze", 
        "Okucia", "Kontrola", "Pakowanie"
    ]
    
    sekwencja_nowa = []
    
    # Generowanie formularza dla każdego kroku
    # Domyślnie dajemy tyle kroków, ile jest procesów w wycenie
    liczba_krokow = len(procesy_wyceny)
    
    for i in range(liczba_krokow):
        col_krok, col_p_w, col_p_t = st.columns([1, 4, 4])
        with col_krok:
            st.write(f"Krok {i+1}")
        with col_p_w:
            # Pokaż informacje o wycenie
            p_wyceny = procesy_wyceny[i]
            st.info(f"Maszyna: {p_wyceny['maszyna_nazwa']} | Proces: {p_wyceny['proces']} ({p_wyceny['czas_standardowy']*p_wyceny['korekta_gabaryt']:.2f}h)")
        with col_p_t:
            # Wybór procesu technologicznego
            domyslny_idx = 0
            if i < len(sekwencja_zapissana):
                # Jeśli jest zapisany, wczytaj go
                zapisany_proc = sekwencja_zapissana[i]['nazwa_procesu']
                if zapisany_proc in kategorie_procesow:
                    domyslny_idx = kategorie_procesow.index(zapisany_proc)
            
            wybrana_kat = st.selectbox(f"Przyporządkuj krok {i+1} do", kategorie_procesow, index=domyslny_idx, key=f"tech_step_{i}")
            
            sekwencja_nowa.append({
                'krok': i + 1,
                'nazwa_procesu': wybrana_kat,
                'przypisany_czas': p_wyceny['czas_standardowy'] * p_wyceny['korekta_gabaryt']
            })
            
    st.write("---")
    
    # Szybka edycja BOM z tego poziomu
    st.markdown("### 2. Szybka edycja BOM")
    bom_rows = database.pobierz_bom_produktu(kod_produktu)
    if bom_rows:
        df_bom = pd.DataFrame([dict(r) for r in bom_rows])
        st.dataframe(df_bom[['kod_materialu', 'nazwa', 'ilosc', 'cena']], use_container_width=True)
    else:
        st.write("Brak BOM w wycenie.")
        
    st.write("---")
    
    if st.button("ZAPISZ KARTĘ TECHNOLOGICZNĄ (ERP)"):
        success = database.zapisz_sekwencje_technologiczna(kod_produktu, sekwencja_nowa)
        if success:
            st.success("Sekwencja technologiczna zapisana pomyślnie!")
        else:
            st.error("Błąd podczas zapisu sekwencji.")

# --- MODUŁ 4: DOKUMENTACJA ---
def modul_dokumentacja():
    st.markdown("<h2 class='main-header'>📖 Dokumentacja 'Krok po kroku'</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Opisy procesów i instrukcje ilustrowane zdjęciami dla działu produkcji.</p>", unsafe_allow_html=True)
    
    kod_produktu = st.text_input("Kod produktu do dokumentacji", value="").strip()
    
    if not kod_produktu:
        st.info("Podaj kod wycenionego produktu, aby wyświetlić lub utworzyć instrukcję wykonania.")
        return
        
    karta = database.pobierz_karte_produktu(kod_produktu)
    if not karta:
        st.error("Produkt nie istnieje w bazie wycen.")
        return
        
    st.write(f"Instrukcja technologiczna dla: **{karta['nazwa']}** ({kod_produktu})")
    
    # Pobieranie aktualnej dokumentacji
    kroki = database.pobierz_dokumentacje_produktu(kod_produktu)
    
    tab1, tab2 = st.tabs(["Instrukcja dla Produkcji", "Edycja / Dodaj Krok"])
    
    with tab1:
        if not kroki:
            st.warning("Brak kroków dokumentacji dla tego produktu.")
        else:
            for k in kroki:
                st.markdown(f"#### Krok {k['krok']}: {k['opis']}")
                if k['zdjecie_path'] and os.path.exists(k['zdjecie_path']):
                    st.image(k['zdjecie_path'], width=600)
                elif k['zdjecie_path']:
                    st.info(f"Zdjęcie (ścieżka): {k['zdjecie_path']}")
                st.write("---")
                
    with tab2:
        st.subheader("Wprowadzanie kroków instrukcji")
        krok_nr = st.number_input("Numer Kroku (Kolejność)", min_value=1, value=len(kroki) + 1)
        opis_kroku = st.text_area("Szczegółowy opis wykonania / uwagi bezpieczeństwa")
        
        st.markdown("**Dodaj zdjęcie / rysunek ilustrujący:**")
        plik_graficzny = st.file_uploader("Wybierz plik graficzny (PNG, JPG)", type=["png", "jpg", "jpeg"])
        
        if st.button("Zapisz Krok Instrukcji"):
            zdjecie_path = None
            if plik_graficzny:
                # Stworzenie katalogu na zdjęcia, jeśli nie istnieje
                os.makedirs("data/images", exist_ok=True)
                sciezka_zapisu = f"data/images/{kod_produktu}_krok_{krok_nr}.jpg"
                with open(sciezka_zapisu, "wb") as f:
                    f.write(plik_graficzny.getbuffer())
                zdjecie_path = sciezka_zapisu
                
            success = database.zapisz_krok_dokumentacji(kod_produktu, krok_nr, opis_kroku, zdjecie_path)
            if success:
                st.success(f"Dodano krok {krok_nr} do dokumentacji!")
                st.rerun()
            else:
                st.error("Nie udało się zapisać kroku.")

# --- MODUŁ 5: WIZUALIZACJA APS (GANTT) ---
def modul_planowanie_aps():
    st.markdown("<h2 class='main-header'>📊 Planowanie Produkcji (APS) i Gantt</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Zarządzanie czasem pracy, omijanie awarii oraz symulacje harmonogramu.</p>", unsafe_allow_html=True)
    
    # 1. Symulacja Awarii (What-If)
    st.sidebar.markdown("### ⚠️ Symulacja Awarii (What-If)")
    maszyny = database.pobierz_maszyny()
    if maszyny:
        wybrana_m_awaria = st.sidebar.selectbox("Wybierz maszynę z awarią", [m['nazwa'] for m in maszyny])
        a_dat = st.sidebar.date_input("Dzień awarii", value=date.today())
        a_start_t = st.sidebar.time_input("Godzina rozpoczęcia", value=time(9, 0))
        a_stop_t = st.sidebar.time_input("Godzina zakończenia", value=time(13, 0))
        
        if st.sidebar.button("Dodaj Awarię do Symulacji"):
            a_start_dt = datetime.combine(a_dat, a_start_t)
            a_stop_dt = datetime.combine(a_dat, a_stop_t)
            st.session_state['awarie_symulacja'][wybrana_m_awaria] = (a_start_dt, a_stop_dt)
            st.sidebar.success(f"Dodano awarię maszyny {wybrana_m_awaria}")
            st.rerun()
            
    if st.session_state['awarie_symulacja']:
        st.sidebar.markdown("**Aktywne awarie w symulacji:**")
        do_usuniecia = []
        for m, (s, e) in st.session_state['awarie_symulacja'].items():
            st.sidebar.write(f"❌ {m}: {s.strftime('%H:%M')} - {e.strftime('%H:%M')}")
            if st.sidebar.button("Usuń", key=f"del_a_{m}"):
                do_usuniecia.append(m)
        if do_usuniecia:
            for m in do_usuniecia:
                del st.session_state['awarie_symulacja'][m]
            st.rerun()
            
    # 2. Generowanie Planu APS
    with st.spinner("Przeliczanie harmonogramu APS..."):
        operacje = scheduler.generuj_harmonogram_aps(wstrzymane_maszyny=st.session_state['awarie_symulacja'])
        
    if not operacje:
        st.warning("Brak zlecanych i wycenionych produktów w systemie do zaplanowania.")
        return
        
    # Wykres Gantta
    st.markdown("### Wykres Gantta")
    fig = scheduler.wizualizuj_harmonogram_gantt(operacje)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
        
    # Analiza Wąskich Gadeł
    st.markdown("### 🚨 Analiza Obciążenia Stanowisk (Wąskie Gardła)")
    aktywne_zam = database.pobierz_zamowienia()
    waskie_gardla = scheduler.identyfikuj_waskie_gardla(aktywne_zam)
    
    if waskie_gardla:
        df_wg = pd.DataFrame(waskie_gardla, columns=["Maszyna", "Suma Godzin Obciążenia"])
        
        col_c1, col_c2 = st.columns([1.5, 1])
        with col_c1:
            st.bar_chart(df_wg.set_index("Maszyna"))
        with col_c2:
            st.dataframe(df_wg, hide_index=True)
            
    # Zrzut planu (lista zadań dla maszyn)
    st.write("---")
    col_d1, col_d2 = st.columns([3, 1])
    with col_d1:
        st.markdown("### 📥 Zrzut Planu Produkcyjnego")
        st.write("Generowanie szczegółowej listy zadań dla operatorów na najbliższą zmianę (2 razy na dobę).")
    with col_d2:
        st.write("")
        st.write("")
        if st.button("Pobierz / Zapisz Plan do ERP"):
            # Aktualizacja planowanych czasów w bazie
            conn = database.get_connection()
            cursor = conn.cursor()
            try:
                for op in operacje:
                    cursor.execute("""
                    UPDATE zamowienia SET 
                        start_planowany = ?, stop_planowany = ?
                    WHERE nr_zamowienia = ?
                    """, (op['Start'].strftime('%Y-%m-%d %H:%M'), op['Koniec'].strftime('%Y-%m-%d %H:%M'), op['Zlecenie']))
                conn.commit()
                st.success("Zapisano planowany czas rozpoczęcia i zakończenia do bazy danych!")
            except Exception as e:
                conn.rollback()
                st.error(f"Błąd zapisu planu: {e}")
            finally:
                conn.close()

    # Wyświetlanie szczegółowej listy operacji
    df_op = pd.DataFrame(operacje)
    df_op['Start'] = df_op['Start'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M'))
    df_op['Koniec'] = df_op['Koniec'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M'))
    st.dataframe(df_op[['Zlecenie', 'Produkt', 'Operacja', 'Maszyna', 'Start', 'Koniec', 'Ilość']], hide_index=True, use_container_width=True)

# --- MODUŁ 6: REALIZACJA (STANOWISKO LAN) ---
def modul_realizacja():
    st.markdown("<h2 class='main-header'>📱 Panel Realizacji Produkcji</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Interfejs operatora na stanowisku produkcyjnym (LAN). Raportowanie czasu pracy.</p>", unsafe_allow_html=True)
    
    maszyny = database.pobierz_maszyny()
    if not maszyny:
        st.error("Brak maszyn w systemie.")
        return
        
    m_nazwy = [m['nazwa'] for m in maszyny]
    wybrana_maszyna = st.selectbox("Wybierz stanowisko / maszynę, przy której pracujesz:", m_nazwy)
    
    # Pobranie zadań dla tej maszyny z ostatniego zapisanego planu w bazie
    st.subheader("Twoja lista zadań (chronologicznie):")
    
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, nr_zamowienia, kod_produktu, ilosc, start_planowany, stop_planowany, status
    FROM zamowienia 
    WHERE status IN ('Wycenione', 'W Produkcji')
    ORDER BY priorytet ASC;
    """)
    zlecenia = cursor.fetchall()
    conn.close()
    
    zadania_maszyny = []
    for z in zlecenia:
        # Sprawdzamy czy dany produkt ma proces na tej maszynie
        wycena_p = database.pobierz_procesy_wyceny_produktu(z['kod_produktu'])
        for p in wycena_p:
            if p['maszyna_nazwa'] == wybrana_maszyna:
                zadania_maszyny.append({
                    'id_zamowienia': z['id'],
                    'nr_zamowienia': z['nr_zamowienia'],
                    'kod_produktu': z['kod_produktu'],
                    'ilosc': z['ilosc'],
                    'proces': p['proces'],
                    'czas_planowany': z['start_planowany'],
                    'status_zamowienia': z['status']
                })
                
    if not zadania_maszyny:
        st.info("Brak zaplanowanych zadań na wybranym stanowisku.")
        return
        
    # Renderowanie listy zadań i opcji start/stop
    for idx, z in enumerate(zadania_maszyny):
        with st.expander(f"⚙️ Zlecenie {z['nr_zamowienia']} - {z['proces']} (Ilość: {z['ilosc']} szt.)"):
            col_info, col_actions = st.columns([2, 1])
            
            with col_info:
                st.write(f"**Produkt:** {z['kod_produktu']}")
                st.write(f"**Planowany start:** {z['czas_planowany'] if z['czas_planowany'] else 'Niezaplanowano'}")
                st.write(f"**Status zlecenia:** {z['status_zamowienia']}")
                
            with col_actions:
                # Sprawdzenie, czy ten proces jest obecnie w toku
                reali = database.pobierz_aktywne_realizacje()
                aktywne = [r for r in reali if r['zamowienie_id'] == z['id_zamowienia'] and r['proces'] == z['proces']]
                
                if aktywne:
                    st.warning("PROCES W TOKU")
                    operator = aktywne[0]['operator']
                    st.write(f"Operator: {operator}")
                    
                    if st.button("ZAKOŃCZ PRACĘ (STOP)", key=f"stop_{idx}"):
                        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        database.zakoncz_proces_realizacji(aktywne[0]['id'], now_str)
                        st.success("Zarejestrowano koniec pracy!")
                        st.rerun()
                else:
                    operator_imie = st.text_input("Imię operatora", value=st.session_state['uzytkownik'], key=f"op_name_{idx}")
                    if st.button("ROZPOCZNIJ PRACĘ (START)", key=f"start_{idx}"):
                        if not operator_imie:
                            st.error("Musisz podać imię operatora.")
                        else:
                            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            database.rozpocznij_proces_realizacji(z['id_zamowienia'], z['proces'], operator_imie, now_str)
                            st.success("Zarejestrowano rozpoczęcie pracy!")
                            st.rerun()

# --- MODUŁ 7: RAPORTY WALIDACJI ---
def modul_walidacja():
    st.markdown("<h2 class='main-header'>📈 Raport Walidacji Norm Czasowych</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Porównanie normatywów wyceny z rzeczywistymi czasami zebranymi z LAN.</p>", unsafe_allow_html=True)
    
    dane = database.pobierz_dane_walidacji_czasow()
    
    if not dane:
        st.warning("Brak zakończonych realizacji w bazie danych do porównania norm.")
        return
        
    df_val = pd.DataFrame([dict(r) for r in dane])
    df_val['Rozbieżność (%)'] = ((df_val['rzeczywisty_czas_sztuka'] - df_val['czas_wyceniony_sztuka']) / df_val['czas_wyceniony_sztuka']) * 100
    
    st.markdown("### Dane porównawcze")
    st.dataframe(
        df_val[['kod_produktu', 'nazwa_produktu', 'proces', 'liczba_zlecen', 'czas_wyceniony_sztuka', 'rzeczywisty_czas_sztuka', 'Rozbieżność (%)']],
        hide_index=True,
        column_config={
            "kod_produktu": "Kod Produktu",
            "nazwa_produktu": "Nazwa",
            "proces": "Proces",
            "liczba_zlecen": "Liczba zleceń",
            "czas_wyceniony_sztuka": st.column_config.NumberColumn("Norma (h/szt)", format="%.3f"),
            "rzeczywisty_czas_sztuka": st.column_config.NumberColumn("Real (h/szt)", format="%.3f"),
            "Rozbieżność (%)": st.column_config.NumberColumn("Odchylenie (%)", format="%.1f")
        }
    )
    
    # Wykres rozbieżności
    st.write("---")
    st.markdown("### Wykres Odchyleń Rzeczywistych Czasów od Normy (%)")
    st.bar_chart(df_val.set_index("proces")["Rozbieżność (%)"])
    
    st.info("💡 Dodatnie odchylenie oznacza, że praca trwała dłużej niż planowano (norma niedoszacowana). Ujemne odchylenie oznacza wykonanie szybsze niż norma (norma przeszacowana).")

# --- MODUŁ: ZARZĄDZANIE UŻYTKOWNIKAMI (ADMINISTRATOR) ---
def modul_zarzadzanie_uzytkownikami():
    st.markdown("<h2 class='main-header'>👥 Zarządzanie Użytkownikami</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Dodawanie i usuwanie kont użytkowników w systemie SWTP.</p>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Lista i Usuwanie Użytkowników", "Dodaj Nowego Użytkownika"])
    
    with tab1:
        st.subheader("Aktualni użytkownicy")
        uzytkownicy = database.pobierz_uzytkownikow()
        if not uzytkownicy:
            st.warning("Brak użytkowników (błąd krytyczny).")
        else:
            df_users = pd.DataFrame([dict(u) for u in uzytkownicy])
            st.dataframe(df_users, hide_index=True, column_config={
                "id": "ID",
                "login": "Nazwa użytkownika (login)",
                "rola": "Rola w systemie"
            }, use_container_width=True)
            
            st.write("---")
            st.subheader("Usuń użytkownika")
            opcje_usuwania = {f"{u['login']} ({u['rola']})": u['id'] for u in uzytkownicy if u['login'] != 'admin'}
            
            if not opcje_usuwania:
                st.info("Brak użytkowników możliwych do usunięcia (nie można usunąć głównego konta 'admin').")
            else:
                wybrany_uzytkownik = st.selectbox("Wybierz użytkownika do usunięcia", list(opcje_usuwania.keys()))
                user_id_do_usunięcia = opcje_usuwania[wybrany_uzytkownik]
                
                if st.button("USUŃ KONTO", type="primary"):
                    success = database.usun_uzytkownika(user_id_do_usunięcia)
                    if success:
                        st.success(f"Pomyślnie usunięto użytkownika {wybrany_uzytkownik}!")
                        st.rerun()
                    else:
                        st.error("Nie udało się usunąć użytkownika.")
                        
    with tab2:
        st.subheader("Tworzenie nowego konta")
        with st.form("nowy_uzytkownik_form"):
            nowy_login = st.text_input("Login / Nazwa użytkownika")
            nowe_haslo = st.text_input("Hasło", type="password")
            nowa_rola = st.selectbox("Rola w systemie", ["Planista", "Konstruktor", "Operator", "Menedżer"])
            
            submit_user = st.form_submit_button("Utwórz użytkownika")
            
            if submit_user:
                if not nowy_login or not nowe_haslo:
                    st.error("Wszystkie pola są wymagane.")
                else:
                    success = database.dodaj_uzytkownika(nowy_login, nowe_haslo, nowa_rola)
                    if success:
                        st.success(f"Pomyślnie utworzono konto dla użytkownika: {nowy_login}!")
                        st.rerun()
                    else:
                        st.error("Użytkownik o takim loginie już istnieje.")

# --- GŁÓWNA LOGIKA STRONY ---
def main():
    if not st.session_state['zalogowany']:
        ekran_logowania()
    else:
        modul = panel_boczny()
        
        if modul == "Harmonogram i Zadania":
            modul_harmonogram()
        elif modul == "Wycena i Karta Produktu":
            modul_wycena()
        elif modul == "Technologia":
            modul_technologia()
        elif modul == "Dokumentacja":
            modul_dokumentacja()
        elif modul == "Wizualizacja APS (Gantt)":
            modul_planowanie_aps()
        elif modul == "Realizacja (Stanowisko LAN)":
            modul_realizacja()
        elif modul == "Raporty Walidacji":
            modul_walidacja()
        elif modul == "Zarządzanie Użytkownikami":
            modul_zarzadzanie_uzytkownikami()

if __name__ == "__main__":
    main()
