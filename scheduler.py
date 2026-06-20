# -*- coding: utf-8 -*-
"""
scheduler.py - Silnik planowania APS (Advanced Planning and Scheduling) dla systemu SWTP.
Zawiera algorytm szeregowania wstecznego (Backward Scheduling),
obsługę kalendarza czasu pracy (8:00-16:00, bez weekendów),
analizę wąskich gardeł, symulację awarii maszyn oraz wizualizację Gantta przez Plotly.
Wszystkie komentarze i nazwy interfejsów są w języku polskim.
"""

from datetime import datetime, timedelta, time
import pandas as pd
import plotly.express as px
import database

# Definicje czasu pracy firmy
POCZATEK_PRACY = time(8, 0, 0)
KONIEC_PRACY = time(16, 0, 0)
DLUGOST_DNIOWKI_H = 8.0

def czy_dzien_roboczy(dt):
    """Sprawdza, czy dzień jest dniem roboczym (poniedziałek - piątek)."""
    return dt.weekday() < 5

def przesun_czas_roboczy(start_dt, godziny, wstecz=False):
    """
    Przesuwa czas o podaną liczbę godzin roboczych (8:00-16:00, omijając weekendy).
    wstecz: jeśli True, planuje czas w tył (dla szeregowania wstecznego).
    """
    obecny_dt = start_dt
    pozostalo_godzin = float(godziny)
    krok = timedelta(minutes=15)
    krok_godziny = 0.25
    
    while pozostalo_godzin > 0:
        if wstecz:
            obecny_dt -= krok
        else:
            obecny_dt += krok
            
        # Omijanie weekendów
        while not czy_dzien_roboczy(obecny_dt):
            if wstecz:
                # Jeśli weekend i idziemy wstecz, przeskakujemy na piątek godz. 16:00
                obecny_dt = datetime.combine(obecny_dt.date() - timedelta(days=1), KONIEC_PRACY)
            else:
                # Jeśli weekend i idziemy w przód, przeskakujemy na poniedziałek godz. 8:00
                obecny_dt = datetime.combine(obecny_dt.date() + timedelta(days=1), POCZATEK_PRACY)
                
        # Sprawdzanie godzin pracy
        cz_dnia = obecny_dt.time()
        if cz_dnia < POCZATEK_PRACY:
            if wstecz:
                # Przeskakujemy na poprzedni dzień roboczy na koniec pracy
                poprzedni_dzien = obecny_dt.date() - timedelta(days=1)
                obecny_dt = datetime.combine(poprzedni_dzien, KONIEC_PRACY)
                while not czy_dzien_roboczy(obecny_dt):
                    obecny_dt = datetime.combine(obecny_dt.date() - timedelta(days=1), KONIEC_PRACY)
            else:
                # Przeskakujemy na 8:00 dzisiejszego dnia
                obecny_dt = datetime.combine(obecny_dt.date(), POCZATEK_PRACY)
        elif cz_dnia > KONIEC_PRACY:
            if wstecz:
                # Przeskakujemy na 16:00 dzisiejszego dnia
                obecny_dt = datetime.combine(obecny_dt.date(), KONIEC_PRACY)
            else:
                # Przeskakujemy na kolejny dzień roboczy na 8:00
                kolejny_dzien = obecny_dt.date() + timedelta(days=1)
                obecny_dt = datetime.combine(kolejny_dzien, POCZATEK_PRACY)
                while not czy_dzien_roboczy(obecny_dt):
                    obecny_dt = datetime.combine(obecny_dt.date() + timedelta(days=1), POCZATEK_PRACY)
                    
        pozostalo_godzin -= krok_godziny
        
    return obecny_dt

def oblicz_czas_procesu(ilosc, czas_std, korekta_gabaryt):
    """Oblicza sumaryczny czas dla danej operacji (ilość sztuk * czas_std * korekta)."""
    return float(ilosc) * float(czas_std) * float(korekta_gabaryt)

def identyfikuj_waskie_gardla(aktywne_zamowienia):
    """
    Analizuje obciążenie maszyn na podstawie zamówień i procesów w wycenie.
    Zwraca słownik maszyn wraz z sumarycznym czasem pracy w godzinach.
    """
    obciazenia = {}
    for zam in aktywne_zamowienia:
        if zam['status'] not in ['Harmonogram', 'Wycenione', 'W Produkcji']:
            continue
        kod_produktu = zam['kod_produktu']
        ilosc = zam['ilosc']
        
        procesy = database.pobierz_procesy_wyceny_produktu(kod_produktu)
        for p in procesy:
            m_nazwa = p['maszyna_nazwa']
            czas_std = p['czas_standardowy']
            korekta = p['korekta_gabaryt']
            czas_calkowity = oblicz_czas_procesu(ilosc, czas_std, korekta)
            
            obciazenia[m_nazwa] = obciazenia.get(m_nazwa, 0.0) + czas_calkowity
            
    # Sortowanie maszyn od najbardziej obciążonej (wąskie gardło na górze)
    waskie_gardla = sorted(obciazenia.items(), key=lambda x: x[1], reverse=True)
    return waskie_gardla

def generuj_harmonogram_aps(wstrzymane_maszyny=None):
    """
    Główny silnik APS planujący produkcję metodą szeregowania wstecznego (Backward Scheduling).
    wstrzymane_maszyny: słownik z awariami np. {'Nazwa Maszyny': (start_awarii_dt, stop_awarii_dt)}
    Zwraca listę zaplanowanych operacji gotowych do wizualizacji i zapisu.
    """
    if wstrzymane_maszyny is None:
        wstrzymane_maszyny = {}
        
    # Pobieramy zamówienia do zaplanowania (status: Wycenione, Harmonogram, W Produkcji)
    zamowienia = database.pobierz_zamowienia()
    zamowienia = [z for z in zamowienia if z['status'] in ['Harmonogram', 'Wycenione', 'W Produkcji']]
    
    # Sortujemy po priorytecie (malejąco) i terminie (rosnąco)
    # Zlecenia z wyższym priorytetem (mniejsza liczba) i wcześniejszym terminem mają pierwszeństwo
    zamowienia = sorted(zamowienia, key=lambda x: (x['priorytet'], x['termin']))
    
    zaplanowane_operacje = []
    # Słownik śledzący obciążenie maszyn w czasie w celu unikania nakładania się zadań
    # machine_occupancy['Maszyna'] = list of tuples (start_dt, stop_dt, nr_zamowienia)
    machine_occupancy = {}
    
    def sprawdz_i_dopasuj_wolny_slot(maszyna, start_proponowany, stop_proponowany, czas_h):
        """
        Sprawdza czy maszyna jest wolna w zadanym przedziale czasowym.
        Jeśli jest zajęta lub w awarii, przesuwa planowane zadanie w tył (dla planowania wstecznego).
        """
        kolizja = True
        dzialanie_start = start_proponowany
        dzialanie_stop = stop_proponowany
        
        while kolizja:
            kolizja = False
            
            # 1. Sprawdzenie awarii maszyny
            if maszyna in wstrzymane_maszyny:
                a_start, a_stop = wstrzymane_maszyny[maszyna]
                # Sprawdzenie nachodzenia
                if not (dzialanie_stop <= a_start or dzialanie_start >= a_stop):
                    # Przesuwamy proponowany koniec na start awarii
                    dzialanie_stop = a_start
                    dzialanie_start = przesun_czas_roboczy(dzialanie_stop, czas_h, wstecz=True)
                    kolizja = True
                    continue
                    
            # 2. Sprawdzenie innych rezerwacji maszyny
            if maszyna in machine_occupancy:
                for rez_start, rez_stop, _ in machine_occupancy[maszyna]:
                    if not (dzialanie_stop <= rez_start or dzialanie_start >= rez_stop):
                        # Przesuwamy proponowany koniec na początek kolidującej rezerwacji
                        dzialanie_stop = rez_start
                        dzialanie_start = przesun_czas_roboczy(dzialanie_stop, czas_h, wstecz=True)
                        kolizja = True
                        break
                        
        return dzialanie_start, dzialanie_stop

    for zam in zamowienia:
        nr_zam = zam['nr_zamowienia']
        kod_prod = zam['kod_produktu']
        ilosc = zam['ilosc']
        deadline_data = datetime.strptime(zam['termin'], '%Y-%m-%d')
        # Ustawiamy termin ostateczny na godzinę 16:00 danego dnia
        deadline_dt = datetime.combine(deadline_data.date(), KONIEC_PRACY)
        
        # Pobieramy procesy technologiczne produktu
        sekwencja = database.pobierz_sekwencje_technologiczna(kod_prod)
        
        if not sekwencja:
            # Jeśli brak sekwencji technologicznej, pobieramy procesy z wyceny i tworzymy tymczasową
            wycena_procesy = database.pobierz_procesy_wyceny_produktu(kod_prod)
            if not wycena_procesy:
                continue
            # Sortujemy je tymczasowo według kolejności dodania
            sekwencja = []
            for idx, p in enumerate(wycena_procesy):
                sekwencja.append({
                    'krok': idx + 1,
                    'nazwa_procesu': p['proces'],
                    'przypisany_czas': p['czas_standardowy'] * p['korekta_gabaryt']
                })
                
        # Sortujemy sekwencję kroków w tył (dla szeregowania wstecznego)
        sekwencja_odwrotna = sorted(sekwencja, key=lambda x: x['krok'], reverse=True)
        
        biezacy_koniec_dt = deadline_dt
        zamowienie_operacje = []
        
        for krok in sekwencja_odwrotna:
            nazwa_proc = krok['nazwa_procesu']
            # Pobieramy maszynę przypisaną do tego procesu z wyceny
            # Dla uproszczenia szukamy w wycenie pierwszej pasującej maszyny wykonującej ten proces
            wycena_p = database.pobierz_procesy_wyceny_produktu(kod_prod)
            maszyna_nazwa = "Ręczne / Inne"
            czas_std = krok['przypisany_czas']
            korekta = 1.0
            
            for wp in wycena_p:
                if wp['proces'] == nazwa_proc:
                    maszyna_nazwa = wp['maszyna_nazwa']
                    czas_std = wp['czas_standardowy']
                    korekta = wp['korekta_gabaryt']
                    break
                    
            czas_operacji_h = oblicz_czas_procesu(ilosc, czas_std, korekta)
            
            # Wstępne wyznaczenie czasu wykonania
            proponowany_start = przesun_czas_roboczy(biezacy_koniec_dt, czas_operacji_h, wstecz=True)
            
            # Rezerwacja czasu maszyny z uwzględnieniem kolizji i awarii
            zaplanowany_start, zaplanowany_stop = sprawdz_i_dopasuj_wolny_slot(
                maszyna_nazwa, proponowany_start, biezacy_koniec_dt, czas_operacji_h
            )
            
            # Zapisujemy rezerwację w harmonogramie maszyny
            if maszyna_nazwa not in machine_occupancy:
                machine_occupancy[maszyna_nazwa] = []
            machine_occupancy[maszyna_nazwa].append((zaplanowany_start, zaplanowany_stop, nr_zam))
            
            zamowienie_operacje.append({
                'Zlecenie': nr_zam,
                'Produkt': kod_prod,
                'Krok': krok['krok'],
                'Operacja': nazwa_proc,
                'Maszyna': maszyna_nazwa,
                'Start': zaplanowany_start,
                'Koniec': zaplanowany_stop,
                'Ilość': ilosc,
                'Termin_Dostawy': deadline_dt
            })
            
            # Kolejna operacja (chronologicznie wcześniejsza) musi skończyć się przed startem obecnej
            biezacy_koniec_dt = zaplanowany_start
            
        # Odwracamy z powrotem, aby zachować chronologię kroków zlecenia
        zaplanowane_operacje.extend(reversed(zamowienie_operacje))
        
    return zaplanowane_operacje

def wizualizuj_harmonogram_gantt(zaplanowane_operacje):
    """
    Tworzy wykres Gantta przy użyciu biblioteki Plotly Express.
    Dopasowuje kolory dla lepszej czytelności i dodaje chmurki informacyjne (Tooltips).
    """
    if not zaplanowane_operacje:
        return None
        
    df = pd.DataFrame(zaplanowane_operacje)
    
    # Przygotowanie etykiet i informacji do hovera
    df['Opis'] = df.apply(
        lambda r: f"Zlecenie: {r['Zlecenie']}<br>Produkt: {r['Produkt']}<br>Operacja: {r['Operacja']}<br>Ilość: {r['Ilość']} szt.<br>Start: {r['Start'].strftime('%Y-%m-%d %H:%M')}<br>Koniec: {r['Koniec'].strftime('%Y-%m-%d %H:%M')}",
        axis=1
    )
    
    # Tworzenie wykresu Gantta (px.timeline)
    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="Koniec", 
        y="Maszyna", 
        color="Zlecenie",
        title="Harmonogram Produkcji SWTP (Wykres Gantta)",
        labels={"Maszyna": "Stanowisko / Maszyna", "Start": "Czas rozpoczęcia", "Koniec": "Czas zakończenia"},
        hover_name="Zlecenie",
        hover_data={"Start": False, "Koniec": False, "Maszyna": True, "Opis": True}
    )
    
    # Poprawa wyglądu wykresu
    fig.update_yaxes(categoryorder="category ascending")
    fig.update_layout(
        xaxis_title="Oś czasu (Praca w godz. 8:00 - 16:00)",
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Outfit"),
        legend_title="Zlecenia",
        title_font=dict(size=18, family="Outfit"),
        font=dict(family="Outfit")
    )
    
    return fig

def generuj_liste_zadan_stanowiskowych(zaplanowane_operacje):
    """
    Grupuje zaplanowane operacje i generuje chronologiczną listę zadań dla poszczególnych maszyn.
    Zwraca słownik: {'Nazwa Maszyny': [Zadanie1, Zadanie2, ...]}
    """
    maszyny_zadania = {}
    for op in zaplanowane_operacje:
        m = op['Maszyna']
        if m not in maszyny_zadania:
            maszyny_zadania[m] = []
        maszyny_zadania[m].append(op)
        
    # Sortowanie zadań na każdej maszynie chronologicznie po starcie
    for m in maszyny_zadania:
        maszyny_zadania[m] = sorted(maszyny_zadania[m], key=lambda x: x['Start'])
        
    return maszyny_zadania
