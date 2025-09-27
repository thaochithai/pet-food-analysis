import os
import re
import pandas as pd
import logging
from bs4 import BeautifulSoup
import glob
from datetime import datetime
import argparse
import json

# set log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amazon_product_parser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AmazonProductHTMLParser:
    def __init__(self, html_dir):
        self.html_dir = html_dir
        if not os.path.exists(html_dir):
            raise ValueError(f"Directory not found: {html_dir}")

    def _extract_asin_from_filename(self, filename):
        asin_match = re.match(r'([A-Z0-9]{10})_', filename)
        if asin_match:
            return asin_match.group(1)
        return None

    def _extract_title(self, soup):
        try:
            # different selectors for title
            title_selectors = [
                "#productTitle",
                "h1.a-size-large",
                "h1.product-title"
            ]
            
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    return element.get_text().strip()
                    
            return None
        except Exception as e:
            logger.warning(f"Error extracting title: {e}")
            return None

    def _extract_brand(self, soup):
        try:
            # multiple selectors for brand
            brand_selectors = [
                "#bylineInfo",
                ".po-brand .a-span9",
                "#brand",
                "a#brand"
            ]
            
            for selector in brand_selectors:
                element = soup.select_one(selector)
                if element:
                    brand_text = element.get_text().strip()
                    
                    #cleAN common prefixes
                    brand_text = re.sub(r'^(Visit the|Brand:|by)\s+', '', brand_text, flags=re.I)
                    brand_text = re.sub(r'\s+Store$', '', brand_text)
                    
                    return brand_text.strip()
            
            # Try from meta tags
            meta_brand = soup.find("meta", attrs={"name": "brand"})
            if meta_brand:
                return meta_brand.get("content", "").strip()
                
            return None
        except Exception as e:
            logger.warning(f"Error extracting brand: {e}")
            return None

    def _extract_categories(self, soup):
        try:
            categories = []
            
            # breadcrumb navigation
            breadcrumbs = soup.select("#wayfinding-breadcrumbs_feature_div li, #wayfinding-breadcrumbs a")
            for crumb in breadcrumbs:
                text = crumb.get_text().strip()
                if text and text not in ["›", "‹", "/"]:
                    categories.append(text)
            
            # dropdown categories
            dropdown_cats = soup.select("#searchDropdownBox option[selected]")
            if dropdown_cats:
                categories.append(dropdown_cats[0].get_text().strip())
            
            return categories if categories else None
        except Exception as e:
            logger.warning(f"Error extracting categories: {e}")
            return None

    def _extract_bullet_points(self, soup):
        try:
            bullet_points = []
            
            # Try feature bullets section
            feature_bullets = soup.select("#feature-bullets li:not(.aok-hidden)")
            for bullet in feature_bullets:
                text = bullet.get_text().strip()
                if text:
                    bullet_points.append(text)
            
            # Try from feature div
            feature_div = soup.select("#featurebullets_feature_div li")
            for bullet in feature_div:
                text = bullet.get_text().strip()
                if text:
                    bullet_points.append(text)
            
            return bullet_points if bullet_points else None
        except Exception as e:
            logger.warning(f"Error extracting bullet points: {e}")
            return None

    def _extract_description(self, soup):
        try:
            # product description section
            description_div = soup.select_one("#productDescription")
            if description_div:
                return description_div.get_text().strip()
            
            # from overview section
            overview = soup.select_one("#aplus, #dpx-aplus-product-description_feature_div")
            if overview:
                return overview.get_text().strip()
            
            # iframed description
            iframe = soup.select_one("#product-description-iframe")
            if iframe:
                return f"[Description in iframe: {iframe.get('src', '')}]"
            
            return None
        except Exception as e:
            logger.warning(f"Error extracting description: {e}")
            return None

    def _extract_bestseller_rank(self, soup):
        try:
            # product detail section
            rank_rows = soup.find_all("tr", id=lambda x: x and "SalesRank" in x)
            if rank_rows:
                return rank_rows[0].get_text().strip()
            
            # Tproduct information section
            rank_section = soup.find(string=re.compile("Best Sellers Rank"))
            if rank_section:
                parent = rank_section.parent
                rank_text = ""
                current = parent
                for _ in range(5): 
                    if current:
                        next_el = current.find_next_sibling()
                        if next_el:
                            rank_text += next_el.get_text().strip() + " "
                            current = next_el
                return rank_text.strip()
            
            # details list
            details_list = soup.select("#detailBulletsWrapper_feature_div li")
            for item in details_list:
                text = item.get_text().strip()
                if "Best Sellers Rank" in text:
                    return text
            
            return None
        except Exception as e:
            logger.warning(f"Error extracting bestseller rank: {e}")
            return None
        
    def _extract_datetime_from_filename(self, filename):
        # match the pattern ASIN_YYYYMMDD_HHMMSS.html
        datetime_match = re.search(r'_(\d{8})_(\d{6})\.html$', filename)
        
        if datetime_match:
            date_str = datetime_match.group(1)  # YYYYMMDD
            time_str = datetime_match.group(2)  # HHMMSS
            
            try:
                dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                return {
                    'scrape_date': dt.strftime("%Y-%m-%d"),
                    'scrape_time': dt.strftime("%H:%M:%S")
                }
            except ValueError:
                pass
        
        # pattern for different date formats
        alt_match = re.search(r'_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})\.html$', filename)
        if alt_match:
            date_str = alt_match.group(1)  # YYYY-MM-DD
            time_str = alt_match.group(2).replace('-', ':')  # HH-MM-SS -> HH:MM:SS
            
            return {
                'scrape_date': date_str,
                'scrape_time': time_str
            }
            
        return {'scrape_date': None, 'scrape_time': None}

    def _extract_price_per_unit(self, soup):
        try:
            # canonical price-per-unit container
            price_per_unit = soup.select_one("span.pricePerUnit")
            if price_per_unit:
                text = price_per_unit.get_text(separator=" ").strip()
                text = text.replace('(', '').replace(')', '')
                text = re.sub(r"\s+", " ", text)
                return text if text else None

            # Alternative selector patterns
            alternative_selectors = [
                ".a-price-per-unit",
                ".pricePerUnit .a-price",
                "[data-testid='price-per-unit']"
            ]
            for selector in alternative_selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(separator=" ").strip()
                    text = re.sub(r"\s+", " ", text)
                    return text if text else None

            return None
        except Exception as e:
            logger.warning(f"Error extracting price per unit: {e}")
            return None
        
    def _extract_product_details_table(self, soup):
        try:
            product_details = {}
            
            # Look for the product details table
            table = soup.select_one("table.a-normal.a-spacing-micro")
            if table:
                rows = table.select("tr")
                for row in rows:
                    # Get the label (first column)
                    label_cell = row.select_one("td:first-child span.a-text-bold")
                    # Get the value (second column)
                    value_cell = row.select_one("td.a-span9 span.po-break-word")
                    
                    if label_cell and value_cell:
                        label = label_cell.get_text().strip()
                        value = value_cell.get_text().strip()
                        product_details[label.lower().replace(' ', '_')] = value
            
            # Alternative approach - look for specific class-based rows
            detail_rows = soup.select("tr[class*='po-']")
            for row in detail_rows:
                label_cell = row.select_one("td:first-child span")
                value_cell = row.select_one("td:last-child span")
                
                if label_cell and value_cell:
                    label = label_cell.get_text().strip()
                    value = value_cell.get_text().strip()
                    product_details[label.lower().replace(' ', '_')] = value
            
            return product_details if product_details else None
        except Exception as e:
            logger.warning(f"Error extracting product details table: {e}")
            return None
        
    def _extract_image_url(self, soup):
        """
        Extract main product image URL from Amazon product page.
        """
        try:
            # Primary landing image
            img = soup.select_one("#landingImage")
            if img and img.get("src"):
                return img["src"]

            # Wrapper fallback
            img = soup.select_one("#imgTagWrapperId img")
            if img and img.get("src"):
                return img["src"]

            # Thumbnail images (first one as fallback)
            thumbnails = soup.select("#altImages img")
            for thumb in thumbnails:
                src = thumb.get("src")
                if src:
                    return src

            return None
        except Exception as e:
            logger.warning(f"Error extracting image URL: {e}")
            return None

    def parse_product_html_file(self, html_file, search_term=None):
        try:
            logger.info(f"Parsing file: {html_file}")
            
            # metadata from filename
            filename = os.path.basename(html_file)
            asin = self._extract_asin_from_filename(filename)
            datetime_info = self._extract_datetime_from_filename(filename)
            
            # HTML file
            with open(html_file, 'r', encoding='utf-8', errors='replace') as f:
                html_content = f.read()
            
            # parse using BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # product details
            title = self._extract_title(soup)
            brand = self._extract_brand(soup)
            categories = self._extract_categories(soup)
            bullet_points = self._extract_bullet_points(soup)
            description = self._extract_description(soup)
            bestseller_rank = self._extract_bestseller_rank(soup)
            price_per_unit = self._extract_price_per_unit(soup)
            product_details = self._extract_product_details_table(soup)
            image_url = self._extract_image_url(soup)
            
            # result object
            result = {
                'asin': asin,
                'search_term': search_term,
                'scrape_date': datetime_info.get('scrape_date'),
                'scrape_time': datetime_info.get('scrape_time'),
                'title': title,
                'brand': brand,
                'categories': categories,
                'bullet_points': bullet_points,
                'description': description,
                'bestseller_rank': bestseller_rank,
                'price_per_unit': price_per_unit,
                'product_details': product_details,
                'image_url': image_url
            }
            
            logger.info(f"Successfully parsed product ASIN {asin}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing file {html_file}: {e}")
            return None

    def parse_search_term_directory(self, search_term):
        all_results = []
        
        # safe search term for directory lookup
        safe_term = re.sub(r'[^a-zA-Z0-9]', '_', search_term)
        term_dir = os.path.join(self.html_dir, safe_term)
        
        if not os.path.exists(term_dir):
            logger.error(f"Search term directory not found: {term_dir}")
            return pd.DataFrame()
        
        # HTML files for this search term
        html_files = glob.glob(os.path.join(term_dir, "*.html"))
        
        for html_file in html_files:
            result = self.parse_product_html_file(html_file, search_term)
            if result:
                all_results.append(result)
        
        if not all_results:
            logger.warning(f"No results found for search term: {search_term}")
            return pd.DataFrame()
        
        # DataFrame
        df = pd.DataFrame(all_results)
        
        # list columns to string for CSV 
        for col in ['categories', 'bullet_points']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: '|'.join(x) if isinstance(x, list) else x)
        
        logger.info(f"Created DataFrame with {len(df)} products for search term: {search_term}")
        return df

    def parse_all_search_terms(self):
        all_results = []
        
        # all search term directories
        search_terms = [d for d in os.listdir(self.html_dir) if os.path.isdir(os.path.join(self.html_dir, d))]
        
        if not search_terms:
            logger.error(f"No search term directories found in {self.html_dir}")
            return pd.DataFrame()
        
        logger.info(f"Found {len(search_terms)} search term directories")
        
        for safe_term in search_terms:
            search_term = safe_term.replace('_', ' ').strip()
            
            df = self.parse_search_term_directory(search_term)
            if not df.empty:
                all_results.append(df)
        
        if not all_results:
            logger.warning("No results found in any search term directory")
            return pd.DataFrame()
        
        combined_df = pd.concat(all_results, ignore_index=True)
        logger.info(f"Created combined DataFrame with {len(combined_df)} products from all search terms")
        
        return combined_df


def main():
    parser = argparse.ArgumentParser(description="parsing HTML files")
    parser.add_argument("--html-dir", required=True, help="directory")
    parser.add_argument("--search-term", help="specific term")
    parser.add_argument("--output", default="amazon_product_results.csv", help="csv")
    parser.add_argument("--format", choices=["csv", "json", "both"], default="both", 
                       help="both csv and json)")
    
    args = parser.parse_args()
    
    try:
        html_parser = AmazonProductHTMLParser(args.html_dir)
        
        if args.search_term:
            logger.info(f"Parsing products for queries: {args.search_term}")
            results_df = html_parser.parse_search_term_directory(args.search_term)
        else:
            logger.info("Parsing products for all queries")
            results_df = html_parser.parse_all_search_terms()
        
        if results_df.empty:
            logger.error("no results were found")
        else:
            if args.format in ["csv", "both"]:
                results_df.to_csv(args.output, index=False, encoding='utf-8-sig')
                logger.info(f"Results saved to {args.output}")
                
            if args.format in ["json", "both"]:
                json_output = args.output.replace('.csv', '.json')
                results_df.to_json(json_output, orient='records', indent=4)
                logger.info(f"Results saved to {json_output}")
    
    except Exception as e:
        logger.error(f"error occurred: {e}")
        raise


if __name__ == "__main__":
    main()