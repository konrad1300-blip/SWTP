# -*- coding: utf-8 -*-
"""
database.py - Moduł obsługi bazy danych SQLite dla systemu SWTP.
Zawiera definicje tabel, mechanizmy importu danych z plików Excel
oraz funkcje pomocnicze do obsługi logiki biznesowej.
Wszystkie komentarze i nazewnictwo interfejsów są w języku polskim.
"""

import sqlite3
import os
import pandas as pd
import hashlib

DB_FILE = 'swtp.db'

def get_connection():
    """Zwraca połączenie z bazą danych SQLite."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Włączenie obsługi kluczy obcych
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def szyfruj_haslo(haslo):
    """Szyfruje hasło za pomocą SHA256 w celach demonstracyjnych."""
    return hashlib.sha256(haslo.encode('utf-8')).hexdigest()

def inicjalizuj_baze():
    """Tworzy tabele w bazie danych, jeśli jeszcze nie istnieją, oraz dodaje domyślnych użytkowników."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabela użytkowników
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS uzytkownicy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL,
        haslo TEXT NOT NULL,
        rola TEXT NOT NULL
    );
    """)

    # 2. Tabela maszyn (importowanych z Maszyny.xlsx)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS maszyny (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nazwa TEXT UNIQUE NOT NULL,
        typ TEXT,
        dzial TEXT,
        zdjecie TEXT,
        dlugosc_ramienia REAL
    );
    """)

    # 3. Tabela procesów maszyn (przypisanie procesów do danej maszyny wraz ze stawką godzinową)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS procesy_maszyn (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        maszyna_id INTEGER NOT NULL,
        proces TEXT NOT NULL,
        koszt_godzina REAL NOT NULL,
        FOREIGN KEY (maszyna_id) REFERENCES maszyny(id) ON DELETE CASCADE,
        UNIQUE(maszyna_id, proces)
    );
    """)

    # 4. Tabela towarów/materiałów (importowanych z Materiały.xlsx)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS materialy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod TEXT UNIQUE NOT NULL,
        nazwa TEXT NOT NULL,
        typ_zasobu TEXT,
        cena REAL DEFAULT 0.0
    );
    """)

    # 5. Tabela powiązań BOM ERP (receptury zaimportowane z Materiały.xlsx)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receptury_seeding (
        kod_produktu TEXT NOT NULL,
        kod_materialu TEXT NOT NULL,
        ilosc REAL NOT NULL,
        PRIMARY KEY (kod_produktu, kod_materialu)
    );
    """)

    # 6. Tabela zamówień (harmonogram i lista zadań)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS zamowienia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nr_zamowienia TEXT UNIQUE NOT NULL,
        klient TEXT,
        kod_produktu TEXT NOT NULL,
        ilosc INTEGER NOT NULL,
        termin DATE NOT NULL,
        priorytet INTEGER DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'Harmonogram', -- 'Harmonogram', 'Do Wyceny', 'Wycenione', 'W Produkcji', 'Zakończone'
        start_planowany TEXT,
        stop_planowany TEXT
    );
    """)

    # 7. Tabela kart produktów (wycenionych)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS karty_produktow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod_produktu TEXT UNIQUE NOT NULL,
        nazwa TEXT NOT NULL,
        plik_kroju TEXT,
        metry_szycia REAL DEFAULT 0.0,
        metry_zgrzewania REAL DEFAULT 0.0,
        pasy_info TEXT, -- Informacja o pasach w formacie JSON lub tekstowym
        inne_informacje TEXT
    );
    """)

    # 8. Tabela rzeczywistego BOM wycenionego produktu (możliwość edycji w technologii)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod_produktu TEXT NOT NULL,
        kod_materialu TEXT NOT NULL,
        ilosc REAL NOT NULL,
        FOREIGN KEY (kod_produktu) REFERENCES karty_produktow(kod_produktu) ON DELETE CASCADE,
        FOREIGN KEY (kod_materialu) REFERENCES materialy(kod) ON DELETE RESTRICT,
        UNIQUE(kod_produktu, kod_materialu)
    );
    """)

    # 9. Tabela procesów wyceny dla produktu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS procesy_wyceny (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod_produktu TEXT NOT NULL,
        maszyna_id INTEGER NOT NULL,
        proces TEXT NOT NULL,
        czas_standardowy REAL NOT NULL, -- w godzinach na 1 sztukę
        korekta_gabaryt REAL DEFAULT 1.0, -- współczynnik korekty (np. 1.2)
        FOREIGN KEY (kod_produktu) REFERENCES karty_produktow(kod_produktu) ON DELETE CASCADE,
        FOREIGN KEY (maszyna_id) REFERENCES maszyny(id) ON DELETE RESTRICT
    );
    """)

    # 10. Tabela procesów technologicznych (sekwencja technologiczna dla ERP)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS procesy_technologiczne (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod_produktu TEXT NOT NULL,
        krok INTEGER NOT NULL,
        nazwa_procesu TEXT NOT NULL, -- np. 'Krojenie', 'Szycie', 'Zgrzewanie HF duży'
        przypisany_czas REAL NOT NULL, -- zsumowany czas z wyceny dla danej grupy procesów (w godzinach na 1 sztukę)
        FOREIGN KEY (kod_produktu) REFERENCES karty_produktow(kod_produktu) ON DELETE CASCADE,
        UNIQUE(kod_produktu, krok)
    );
    """)

    # 11. Tabela dokumentacji produkcyjnej "Krok po kroku"
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS krok_po_kroku (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod_produktu TEXT NOT NULL,
        krok INTEGER NOT NULL,
        opis TEXT NOT NULL,
        zdjecie_path TEXT,
        FOREIGN KEY (kod_produktu) REFERENCES karty_produktow(kod_produktu) ON DELETE CASCADE,
        UNIQUE(kod_produktu, krok)
    );
    """)

    # 12. Tabela realizacji produkcji (odczyty z LAN w czasie rzeczywistym)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS realizacja (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zamowienie_id INTEGER NOT NULL,
        proces TEXT NOT NULL,
        operator TEXT NOT NULL,
        start_time TEXT NOT NULL,
        stop_time TEXT,
        status TEXT NOT NULL DEFAULT 'Rozpoczęte', -- 'Rozpoczęte', 'Wstrzymane', 'Zakończone'
        FOREIGN KEY (zamowienie_id) REFERENCES zamowienia(id) ON DELETE CASCADE
    );
    """)

    # Utworzenie indeksów zwiększających wydajność wyszukiwania
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_materialy_kod ON materialy(kod);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_materialy_nazwa ON materialy(nazwa);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_receptury_seeding_kod ON receptury_seeding(kod_produktu);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bom_kod_produktu ON bom(kod_produktu);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_procesy_wyceny_kod ON procesy_wyceny(kod_produktu);")

    # Dodanie domyślnych użytkowników
    domyslni_uzytkownicy = [
        ('admin', 'admin', 'Menedżer'),
        ('planista', 'planista', 'Planista'),
        ('technolog', 'technolog', 'Technolog'),
        ('zamowienia', 'zamowienia', 'Zamówienia'),
        ('operator', 'operator', 'Operator')
    ]
    for login, haslo, rola in domyslni_uzytkownicy:
        cursor.execute("SELECT id FROM uzytkownicy WHERE login = ?", (login,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO uzytkownicy (login, haslo, rola) VALUES (?, ?, ?)",
                           (login, szyfruj_haslo(haslo), rola))

    conn.commit()
    conn.close()

def importuj_dane_excel(status_callback=None):
    """
    Importuje dane maszyn i materiałów z plików Excel.
    status_callback: funkcja przyjmująca stringa do raportowania postępu.
    """
    if status_callback:
        status_callback("Rozpoczęto import plików Excel...")

    conn = get_connection()
    cursor = conn.cursor()

    # 1. Import Maszyn
    sciezka_maszyny = 'data/Maszyny.xlsx'
    if os.path.exists(sciezka_maszyny):
        if status_callback:
            status_callback("Wczytywanie Maszyny.xlsx...")
        df_m = pd.read_excel(sciezka_maszyny, header=1)
        
        # Czyszczenie starych maszyn
        cursor.execute("DELETE FROM procesy_maszyn;")
        cursor.execute("DELETE FROM maszyny;")
        
        licznik_maszyn = 0
        for _, row in df_m.iterrows():
            nazwa = str(row['Nr. Maszyny Hans Aa']).strip()
            if not nazwa or nazwa == 'nan':
                continue
            typ = str(row['Typ Maszyny']) if pd.notna(row['Typ Maszyny']) else None
            dzial = str(row['Dział']) if pd.notna(row['Dział']) else None
            zdjecie = str(row['Zdjęcie Maszyny']) if pd.notna(row['Zdjęcie Maszyny']) else None
            proces = str(row['Proces']) if pd.notna(row['Proces']) else 'Inny'
            dl_ramienia = float(row['Długość ramienia']) if pd.notna(row['Długość ramienia']) and isinstance(row['Długość ramienia'], (int, float)) else None
            
            try:
                cursor.execute("""
                INSERT OR IGNORE INTO maszyny (nazwa, typ, dzial, zdjecie, dlugosc_ramienia)
                VALUES (?, ?, ?, ?, ?)
                """, (nazwa, typ, dzial, zdjecie, dl_ramienia))
                
                # Pobierz id wstawionej maszyny
                cursor.execute("SELECT id FROM maszyny WHERE nazwa = ?", (nazwa,))
                maszyna_id = cursor.fetchone()[0]
                
                # Dodanie procesu domyślnego dla maszyny ze stawką 100 PLN/h
                cursor.execute("""
                INSERT OR IGNORE INTO procesy_maszyn (maszyna_id, proces, koszt_godzina)
                VALUES (?, ?, ?)
                """, (maszyna_id, proces, 100.0))
                
                licznik_maszyn += 1
            except Exception as e:
                print(f"Błąd przy imporcie maszyny {nazwa}: {e}")
                
        if status_callback:
            status_callback(f"Pomyślnie zaimportowano {licznik_maszyn} maszyn z procesami domyślnymi.")
    else:
        if status_callback:
            status_callback("Ostrzeżenie: Brak pliku data/Maszyny.xlsx - pominięto maszyn.")

    # 2. Import Materiałów i Receptur
    sciezka_materialy = 'data/Materiały.xlsx'
    if os.path.exists(sciezka_materialy):
        if status_callback:
            status_callback("Wczytywanie Materiały.xlsx (to może chwilę potrwać, plik ma ok. 260k wierszy)...")
        
        df_mat = pd.read_excel(sciezka_materialy, sheet_name='TechnologieMaterialy')
        
        if status_callback:
            status_callback("Wczytano Excel. Rozpoczęto przetwarzanie unikalnych surowców i towarów...")
            
        # Zapis unikalnych materiałów na podstawie Twr_Kod
        df_unique = df_mat[['Twr_Kod', 'Twr_Nazwa', 'TypZasobu']].drop_duplicates(subset=['Twr_Kod'])
        
        cursor.execute("DELETE FROM materialy;")
        cursor.execute("DELETE FROM receptury_seeding;")
        
        # Szybki zapis do SQLite za pomocą sqlite3.executemany
        materialy_dane = []
        for _, row in df_unique.iterrows():
            kod = str(row['Twr_Kod']).strip()
            nazwa = str(row['Twr_Nazwa']) if pd.notna(row['Twr_Nazwa']) else kod
            typ = str(row['TypZasobu']) if pd.notna(row['TypZasobu']) else 'Surowiec'
            if kod and kod != 'nan':
                materialy_dane.append((kod, nazwa, typ, 0.0)) # domyślna cena 0.0
                
        cursor.executemany("""
        INSERT OR IGNORE INTO materialy (kod, nazwa, typ_zasobu, cena)
        VALUES (?, ?, ?, ?)
        """, materialy_dane)
        
        if status_callback:
            status_callback(f"Zapisano {len(materialy_dane)} unikalnych towarów w bazie. Przetwarzanie receptur BOM...")
            
        # Zapis powiązań BOM
        df_bom = df_mat[['PTE_Kod', 'Twr_Kod', 'PTZ_Ilosc']].drop_duplicates(subset=['PTE_Kod', 'Twr_Kod'])
        receptury_dane = []
        for _, row in df_bom.iterrows():
            parent = str(row['PTE_Kod']).strip()
            component = str(row['Twr_Kod']).strip()
            ilosc = float(row['PTZ_Ilosc']) if pd.notna(row['PTZ_Ilosc']) else 1.0
            
            if parent and parent != 'nan' and component and component != 'nan':
                receptury_dane.append((parent, component, ilosc))
                
        cursor.executemany("""
        INSERT OR IGNORE INTO receptury_seeding (kod_produktu, kod_materialu, ilosc)
        VALUES (?, ?, ?)
        """, receptury_dane)
        
        if status_callback:
            status_callback(f"Pomyślnie zaimportowano {len(receptury_dane)} powiązań receptur BOM.")
    else:
        if status_callback:
            status_callback("Ostrzeżenie: Brak pliku data/Materiały.xlsx - pominięto import materiałów.")
            
    conn.commit()
    conn.close()
    if status_callback:
        status_callback("Import zakończony sukcesem!")

def loguj_uzytkownika(login, haslo):
    """Sprawdza login i hasło. Zwraca rolę i login użytkownika w przypadku sukcesu lub None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT rola FROM uzytkownicy WHERE login = ? AND haslo = ?", (login, szyfruj_haslo(haslo)))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row['rola']
    return None

# --- OBSŁUGA MASZYN ---
def pobierz_maszyny():
    """Zwraca listę wszystkich maszyn."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM maszyny ORDER BY nazwa;")
    rows = cursor.fetchall()
    conn.close()
    return rows

def dodaj_maszyne(nazwa, typ, dzial, zdjecie, dl_ramienia):
    """Dodaje nową maszynę."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO maszyny (nazwa, typ, dzial, zdjecie, dlugosc_ramienia)
        VALUES (?, ?, ?, ?, ?)
        """, (nazwa, typ, dzial, zdjecie, dl_ramienia))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def pobierz_procesy_maszyny(maszyna_id):
    """Zwraca listę procesów dla danej maszyny."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM procesy_maszyn WHERE maszyna_id = ? ORDER BY proces;", (maszyna_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def dodaj_proces_do_maszyny(maszyna_id, proces, koszt_godzina):
    """Dodaje proces do maszyny ze stawką godzinową."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO procesy_maszyn (maszyna_id, proces, koszt_godzina)
        VALUES (?, ?, ?)
        """, (maszyna_id, proces, koszt_godzina))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Aktualizacja, jeśli już istnieje
        cursor.execute("""
        UPDATE procesy_maszyn SET koszt_godzina = ?
        WHERE maszyna_id = ? AND proces = ?
        """, (koszt_godzina, maszyna_id, proces))
        conn.commit()
        return True
    finally:
        conn.close()

# --- OBSŁUGA MATERIAŁÓW ---
def szukaj_materialów(fraza, limit=100):
    """Wyszukuje materiały po kodzie lub nazwie."""
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
    SELECT * FROM materialy 
    WHERE kod LIKE ? OR nazwa LIKE ? 
    ORDER BY kod 
    LIMIT ?
    """
    fraza_sql = f"%{fraza}%"
    cursor.execute(sql, (fraza_sql, fraza_sql, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows

def aktualizuj_cene_materialu(kod, nowa_cena):
    """Aktualizuje cenę towaru w bazie."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE materialy SET cena = ? WHERE kod = ?", (nowa_cena, kod))
    conn.commit()
    conn.close()

# --- OBSŁUGA ZAMÓWIEŃ (HARMONOGRAM) ---
def pobierz_zamowienia(status_filter=None):
    """Zwraca listę zamówień, opcjonalnie przefiltrowaną po statusie."""
    conn = get_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute("SELECT * FROM zamowienia WHERE status = ? ORDER BY priorytet ASC, termin ASC;", (status_filter,))
    else:
        cursor.execute("SELECT * FROM zamowienia ORDER BY priorytet ASC, termin ASC;")
    rows = cursor.fetchall()
    conn.close()
    return rows

def dodaj_zamowienie(nr_zamowienia, klient, kod_produktu, ilosc, termin, priorytet=1):
    """Dodaje nowe zapytanie/zamówienie."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Automatyczne ustawienie statusu. Jeśli produkt jest już wyceniony (istnieje w karty_produktow), status to 'Wycenione', w przeciwnym razie 'Do Wyceny'
    cursor.execute("SELECT id FROM karty_produktow WHERE kod_produktu = ?", (kod_produktu,))
    istnieje_wycena = cursor.fetchone()
    status = 'Wycenione' if istnieje_wycena else 'Do Wyceny'
    
    try:
        cursor.execute("""
        INSERT INTO zamowienia (nr_zamowienia, klient, kod_produktu, ilosc, termin, priorytet, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nr_zamowienia, klient, kod_produktu, ilosc, termin, priorytet, status))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def aktualizuj_kolejke_harmonogramu(nowa_kolejnosc_ids):
    """Aktualizuje priorytety zamówień na podstawie nowej kolejności w liście."""
    conn = get_connection()
    cursor = conn.cursor()
    for index, order_id in enumerate(nowa_kolejnosc_ids):
        cursor.execute("UPDATE zamowienia SET priorytet = ? WHERE id = ?", (index + 1, order_id))
    conn.commit()
    conn.close()

def zmien_status_zamowienia(order_id, nowy_status):
    """Zmienia status zamówienia."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE zamowienia SET status = ? WHERE id = ?", (nowy_status, order_id))
    conn.commit()
    conn.close()

# --- OBSŁUGA WYCEN I KART PRODUKTÓW ---
def pobierz_karte_produktu(kod_produktu):
    """Pobiera kartę produktu na podstawie kodu."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM karty_produktow WHERE kod_produktu = ?", (kod_produktu,))
    row = cursor.fetchone()
    conn.close()
    return row

def pobierz_recepture_seeding(kod_produktu):
    """Pobiera historyczną recepturę zaimportowaną z ERP (Materiały.xlsx) w celu ułatwienia tworzenia nowej wyceny."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.kod_materialu, r.ilosc, m.nazwa, m.typ_zasobu, m.cena
    FROM receptury_seeding r
    JOIN materialy m ON r.kod_materialu = m.kod
    WHERE r.kod_produktu = ?
    """, (kod_produktu,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def stworz_karte_produktu_i_wycene(kod_produktu, nazwa, plik_kroju, metry_szycia, metry_zgrzewania, pasy_info, inne_info, bom_list, procesy_list):
    """
    Tworzy lub aktualizuje kartę produktu, zapisuje BOM oraz procesy wyceny.
    bom_list: lista słowników [{'kod_materialu': x, 'ilosc': y}]
    procesy_list: lista słowników [{'maszyna_id': x, 'proces': y, 'czas_standardowy': z, 'korekta_gabaryt': w}]
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Zapis/Aktualizacja karty produktu
        cursor.execute("SELECT id FROM karty_produktow WHERE kod_produktu = ?", (kod_produktu,))
        istnieje = cursor.fetchone()
        
        if istnieje:
            cursor.execute("""
            UPDATE karty_produktow 
            SET nazwa = ?, plik_kroju = ?, metry_szycia = ?, metry_zgrzewania = ?, pasy_info = ?, inne_informacje = ?
            WHERE kod_produktu = ?
            """, (nazwa, plik_kroju, metry_szycia, metry_zgrzewania, pasy_info, inne_info, kod_produktu))
        else:
            cursor.execute("""
            INSERT INTO karty_produktow (kod_produktu, nazwa, plik_kroju, metry_szycia, metry_zgrzewania, pasy_info, inne_informacje)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (kod_produktu, nazwa, plik_kroju, metry_szycia, metry_zgrzewania, pasy_info, inne_info))
            
        # 2. Czyszczenie starego BOM i starych procesów
        cursor.execute("DELETE FROM bom WHERE kod_produktu = ?", (kod_produktu,))
        cursor.execute("DELETE FROM procesy_wyceny WHERE kod_produktu = ?", (kod_produktu,))
        
        # 3. Zapis nowego BOM
        for component in bom_list:
            cursor.execute("""
            INSERT INTO bom (kod_produktu, kod_materialu, ilosc)
            VALUES (?, ?, ?)
            """, (kod_produktu, component['kod_materialu'], component['ilosc']))
            
        # 4. Zapis procesów wyceny
        for proc in procesy_list:
            cursor.execute("""
            INSERT INTO procesy_wyceny (kod_produktu, maszyna_id, proces, czas_standardowy, korekta_gabaryt)
            VALUES (?, ?, ?, ?, ?)
            """, (kod_produktu, proc['maszyna_id'], proc['proces'], proc['czas_standardowy'], proc.get('korekta_gabaryt', 1.0)))
            
        # 5. Aktualizacja statusu zamówień powiązanych z tym produktem z 'Do Wyceny' na 'Wycenione'
        cursor.execute("UPDATE zamowienia SET status = 'Wycenione' WHERE kod_produktu = ? AND status = 'Do Wyceny'", (kod_produktu,))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Błąd przy zapisie wyceny: {e}")
        return False
    finally:
        conn.close()

def pobierz_bom_produktu(kod_produktu):
    """Zwraca BOM (zestawienie materiałów) zapisanego produktu."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT b.kod_materialu, b.ilosc, m.nazwa, m.typ_zasobu, m.cena
    FROM bom b
    JOIN materialy m ON b.kod_materialu = m.kod
    WHERE b.kod_produktu = ?
    """, (kod_produktu,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def pobierz_procesy_wyceny_produktu(kod_produktu):
    """Zwraca listę procesów wyceny zapisanego produktu."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT p.*, m.nazwa as maszyna_nazwa
    FROM procesy_wyceny p
    JOIN maszyny m ON p.maszyna_id = m.id
    WHERE p.kod_produktu = ?
    """, (kod_produktu,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- OBSŁUGA TECHNOLOGII (SEKWENCJA DLA ERP) ---
def zapisz_sekwencje_technologiczna(kod_produktu, sekwencja_list):
    """
    Zapisuje lub aktualizuje listę kroków technologicznych dla produktu.
    sekwencja_list: lista słowników [{'krok': 1, 'nazwa_procesu': 'Krojenie', 'przypisany_czas': 0.5}]
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM procesy_technologiczne WHERE kod_produktu = ?", (kod_produktu,))
        for seq in sekwencja_list:
            cursor.execute("""
            INSERT INTO procesy_technologiczne (kod_produktu, krok, nazwa_procesu, przypisany_czas)
            VALUES (?, ?, ?, ?)
            """, (kod_produktu, seq['krok'], seq['nazwa_procesu'], seq['przypisany_czas']))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Błąd przy zapisie technologii: {e}")
        return False
    finally:
        conn.close()

def pobierz_sekwencje_technologiczna(kod_produktu):
    """Pobiera listę kroków technologicznych produktu."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM procesy_technologiczne WHERE kod_produktu = ? ORDER BY krok ASC;", (kod_produktu,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- OBSŁUGA DOKUMENTACJI ---
def zapisz_krok_dokumentacji(kod_produktu, krok, opis, zdjecie_path):
    """Zapisuje jeden krok dokumentacji ze zdjęciem."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT OR REPLACE INTO krok_po_kroku (kod_produktu, krok, opis, zdjecie_path)
        VALUES (?, ?, ?, ?)
        """, (kod_produktu, krok, opis, zdjecie_path))
        conn.commit()
        return True
    except Exception as e:
        print(f"Błąd przy zapisie dokumentacji: {e}")
        return False
    finally:
        conn.close()

def pobierz_dokumentacje_produktu(kod_produktu):
    """Zwraca dokumentację krok po kroku dla produktu."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM krok_po_kroku WHERE kod_produktu = ? ORDER BY krok ASC;", (kod_produktu,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- REALIZACJA I RAPORTOWANIE Z LAN (STANOWISKA) ---
def rozpocznij_proces_realizacji(zamowienie_id, proces, operator, start_time):
    """Zapisuje rozpoczęcie procesu produkcyjnego na stanowisku operatora."""
    conn = get_connection()
    cursor = conn.cursor()
    # Zmiana statusu zamówienia na 'W Produkcji' przy rozpoczęciu pierwszego procesu
    cursor.execute("UPDATE zamowienia SET status = 'W Produkcji' WHERE id = ?", (zamowienie_id,))
    cursor.execute("""
    INSERT INTO realizacja (zamowienie_id, proces, operator, start_time, status)
    VALUES (?, ?, ?, ?, 'Rozpoczęte')
    """, (zamowienie_id, proces, operator, start_time))
    conn.commit()
    conn.close()

def zakoncz_proces_realizacji(realizacja_id, stop_time):
    """Kończy proces produkcyjny, rejestrując czas stop."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE realizacja 
    SET stop_time = ?, status = 'Zakończone'
    WHERE id = ?
    """, (stop_time, realizacja_id))
    conn.commit()
    conn.close()

def pobierz_aktywne_realizacje():
    """Pobiera realizowane obecnie procesy (status 'Rozpoczęte')."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.*, z.nr_zamowienia, z.kod_produktu, z.ilosc
    FROM realizacja r
    JOIN zamowienia z ON r.zamowienie_id = z.id
    WHERE r.status = 'Rozpoczęte'
    ORDER BY r.start_time DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def pobierz_historie_realizacji(zamowienie_id=None):
    """Pobiera historię realizacji dla wybranego zamówienia lub wszystkich zrealizowanych procesów."""
    conn = get_connection()
    cursor = conn.cursor()
    if zamowienie_id:
        cursor.execute("""
        SELECT r.*, z.nr_zamowienia, z.kod_produktu
        FROM realizacja r
        JOIN zamowienia z ON r.zamowienie_id = z.id
        WHERE r.zamowienie_id = ?
        ORDER BY r.start_time DESC;
        """, (zamowienie_id,))
    else:
        cursor.execute("""
        SELECT r.*, z.nr_zamowienia, z.kod_produktu
        FROM realizacja r
        JOIN zamowienia z ON r.zamowienie_id = z.id
        ORDER BY r.start_time DESC;
        """)
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- WALIDACJA CZASÓW ---
def pobierz_dane_walidacji_czasow():
    """
    Zwraca porównanie czasów normatywnych z wyceny do rzeczywistych czasów z realizacji.
    Oblicza różnice w celach walidacji norm.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # Pobiera zsumowane rzeczywiste czasy procesów w godzinach dla każdego produktu i procesu i porównuje z normatywem w wycenie
    sql = """
    SELECT 
        z.kod_produktu,
        kp.nazwa as nazwa_produktu,
        r.proces,
        COUNT(DISTINCT r.zamowienie_id) as liczba_zlecen,
        AVG((strftime('%s', r.stop_time) - strftime('%s', r.start_time)) / 3600.0 / z.ilosc) as rzeczywisty_czas_sztuka,
        MAX(pw.czas_standardowy * pw.korekta_gabaryt) as czas_wyceniony_sztuka
    FROM realizacja r
    JOIN zamowienia z ON r.zamowienie_id = z.id
    JOIN karty_produktow kp ON z.kod_produktu = kp.kod_produktu
    JOIN procesy_wyceny pw ON kp.kod_produktu = pw.kod_produktu AND pw.proces = r.proces
    WHERE r.status = 'Zakończone' AND r.stop_time IS NOT NULL
    GROUP BY z.kod_produktu, r.proces;
    """
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- ZARZĄDZANIE UŻYTKOWNIKAMI (ADMINISTRATOR) ---
def pobierz_uzytkownikow():
    """Zwraca listę wszystkich użytkowników (bez skrótów haseł)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, login, rola FROM uzytkownicy ORDER BY login;")
    rows = cursor.fetchall()
    conn.close()
    return rows

def dodaj_uzytkownika(login, haslo, rola):
    """Dodaje nowego użytkownika z zaszyfrowanym hasłem."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO uzytkownicy (login, haslo, rola)
        VALUES (?, ?, ?)
        """, (login, szyfruj_haslo(haslo), rola))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def usun_uzytkownika(user_id):
    """Usuwa użytkownika na podstawie ID. Nie pozwala usunąć użytkownika 'admin'."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Sprawdzenie czy nie usuwamy głównego admina
        cursor.execute("SELECT login FROM uzytkownicy WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row['login'] == 'admin':
            return False
            
        cursor.execute("DELETE FROM uzytkownicy WHERE id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Błąd przy usuwaniu użytkownika: {e}")
        return False
    finally:
        conn.close()

