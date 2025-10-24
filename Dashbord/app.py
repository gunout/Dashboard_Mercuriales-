# app.py
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template
import re
import io
import time
from urllib.parse import urljoin
from datetime import datetime
import pdfplumber

app = Flask(__name__)

MAIN_PAGE_URL = "https://daaf.reunion.agriculture.gouv.fr/les-mercuriales-r49.html"

# --- ÉTAPE FINALE : Extraction des données depuis une page avec PDF ---
def extract_data_from_pdf_page(url, annee, type_marche):
    """Télécharge le PDF le plus récent et extrait les données de TOUTES ses pages."""
    print(f"      -> Tentative d'extraction de PDF sur la page : {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links = [link for link in soup.find_all('a', href=True) if link['href'].endswith('.pdf')]
        
        if not pdf_links:
            print("      -> ERREUR : Aucun lien PDF trouvé sur cette page.")
            return []
        
        print(f"      -> {len(pdf_links)} lien(s) PDF trouvé(s) sur la page.")

        latest_pdf_url = None
        latest_date = None
        for link_tag in pdf_links:
            pdf_url = urljoin(url, link_tag['href'])
            date_match = re.search(r'/(\d{8})-', pdf_url)
            if date_match:
                try:
                    pdf_date = datetime.strptime(date_match.group(1), "%Y%m%d")
                    if latest_date is None or pdf_date > latest_date:
                        latest_date = pdf_date
                        latest_pdf_url = pdf_url
                except ValueError: continue
        
        if not latest_pdf_url:
            print("      -> INFO : Impossible de déterminer le PDF le plus récent par la date. Sélection du dernier PDF de la liste comme alternative.")
            if pdf_links:
                latest_pdf_url = urljoin(url, pdf_links[-1]['href'])
            else:
                return []
            
        print(f"      -> PDF sélectionné pour l'extraction : {latest_pdf_url.split('/')[-1]}")

        pdf_response = requests.get(latest_pdf_url, headers=headers, timeout=30)
        pdf_response.raise_for_status()

        data = []
        with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
            # --- NOUVEAU : On boucle sur toutes les pages du PDF ---
            print(f"      -> Le PDF a {len(pdf.pages)} page(s). Analyse de toutes les pages.")
            for i, page in enumerate(pdf.pages):
                table = page.extract_table()
                
                if not table:
                    continue # On passe à la page suivante s'il n'y a pas de tableau
                
                # L'en-tête n'est probablement que sur la première page.
                # On saute donc la première ligne uniquement pour la première page.
                rows_to_process = table[1:] if i == 0 else table

                for row in rows_to_process:
                    if len(row) >= 3 and row[0] and row[2]:
                        try:
                            produit = row[0].strip()
                            prix_str = row[2].strip().replace(',', '.')
                            prix = float(prix_str)
                            
                            date_obj = latest_date.strftime('%Y-%m-%d') if latest_date else f"{annee}-01-01"

                            data.append({
                                "date": date_obj,
                                "produit": produit,
                                "prix": prix,
                                "unite": "kg",
                                "marche": type_marche,
                                "annee": int(annee)
                            })
                        except (ValueError, IndexError):
                            continue
        print(f"      -> Extraction réussie. {len(data)} lignes de données extraites de ce PDF.")
        return data
    except Exception as e:
        print(f"      -> ERREUR CRITIQUE lors de l'extraction des données de {url}: {e}")
        return []

# --- LOGIQUE DE NAVIGATION ADAPTATIVE (inchangée) ---
def navigate_and_scrape(start_url, annee, type_marche):
    print(f"--- Navigation depuis : {start_url} ({annee} - {type_marche}) ---")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(start_url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        sub_category_links = {}
        for link_tag in soup.find_all('a', href=True):
            if re.search(r'-r\d+\.html$', link_tag['href']):
                name = link_tag.get_text(strip=True)
                if 'fruits' in name or 'légumes' in name:
                    sub_category_links['fruits_et_legumes'] = urljoin(start_url, link_tag['href'])
        
        if sub_category_links:
            print(f"  -> Sous-catégories trouvées. Navigation vers 'fruits_et_legumes'.")
            return navigate_and_scrape(sub_category_links['fruits_et_legumes'], annee, type_marche)

        week_links = []
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            if re.search(r'semaine-\d+-\d+', href):
                week_links.append(urljoin(start_url, href))
        
        if week_links:
            print(f"  -> Liste de {len(week_links)} semaines trouvée.")
            all_data = []
            for week_url in week_links:
                print(f"    -> Scraping de la semaine : {week_url.split('/')[-1]}")
                all_data.extend(extract_data_from_pdf_page(week_url, annee, type_marche))
                time.sleep(1)
            return all_data

        month_links = []
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            if re.search(r'(janvier|février|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|décembre)-\d{4}', href, re.IGNORECASE):
                month_links.append(urljoin(start_url, href))

        if month_links:
            print(f"  -> Liste de {len(month_links)} mois trouvée.")
            all_data = []
            for month_url in month_links:
                print(f"    -> Scraping du mois : {month_url.split('/')[-1]}")
                all_data.extend(extract_data_from_pdf_page(month_url, annee, type_marche))
                time.sleep(1)
            return all_data

        print("  -> Structure de liste non trouvée, recherche directe de PDFs sur cette page.")
        return extract_data_from_pdf_page(start_url, annee, type_marche)

    except Exception as e:
        print(f"Erreur de navigation sur {start_url}: {e}")
        return []

# --- Fonctions de découverte des liens (inchangées) ---
def get_year_links_from_main_page(url):
    print(f"Recherche des années sur la page principale : {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        year_links = {}
        for link_tag in soup.find_all('a', href=True):
            link_text = link_tag.get_text(strip=True)
            year_match = re.search(r'(\d{4})', link_text)
            if year_match:
                annee = year_match.group(1)
                full_url = urljoin(url, link_tag['href'])
                if full_url != url:
                    year_links[annee] = full_url
        print(f"  -> Années trouvées : {sorted(year_links.keys(), reverse=True)}")
        return year_links
    except Exception as e:
        print(f"Erreur lors de la recherche des années : {e}")
        return {}

def get_mercuriale_links_from_year_page(url):
    print(f"Recherche des pages de marché sur l'année : {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        market_links = {}
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            if re.search(r'-r\d+\.html$', href):
                market_name = link_tag.get_text(strip=True).lower()
                full_url = urljoin(url, href)
                if "gros" in market_name: type_marche = "gros"
                elif "détail" in market_name: type_marche = "detail"
                elif "épiceries" in market_name: type_marche = "bio_epiceries"
                elif "producteurs" in market_name and "bio" in market_name: type_marche = "bio_producteurs"
                else: continue
                market_links[type_marche] = full_url
        print(f"  -> Pages de marché trouvées : {list(market_links.keys())}")
        return market_links
    except Exception as e:
        print(f"Erreur lors de la recherche des liens sur {url}: {e}")
        return {}

# --- Flask App ---
all_data_cache = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data_route():
    global all_data_cache
    if not all_data_cache:
        print("Le cache est vide. Lancement du scraping complet...")
        year_urls = get_year_links_from_main_page(MAIN_PAGE_URL)
        for annee, year_url in year_urls.items():
            market_urls = get_mercuriale_links_from_year_page(year_url)
            for type_marche, market_url in market_urls.items():
                scraped_data = navigate_and_scrape(market_url, annee, type_marche)
                all_data_cache.extend(scraped_data)
        print(f"Scraping terminé. {len(all_data_cache)} lignes de données mises en cache.")
    return jsonify(all_data_cache)

if __name__ == '__main__':
    with app.app_context():
        get_data_route()
    app.run(debug=True, port=5000)