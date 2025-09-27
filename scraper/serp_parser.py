import os
import re
import pandas as pd
import logging
from bs4 import BeautifulSoup
import glob
from datetime import datetime
import argparse
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amazon_parser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AmazonSearchHTMLParser:
    def __init__(self, html_dir):
        """
        Initialize the parser with the directory containing HTML files
        
        Args:
            html_dir (str): Path to the directory containing scraped HTML files
        """
        self.html_dir = html_dir
        if not os.path.exists(html_dir):
            raise ValueError(f"Directory not found: {html_dir}")

    def _extract_page_number(self, filename):
        """Extract page number from filename"""
        page_match = re.search(r'page(\d+)', filename)
        if page_match:
            return int(page_match.group(1))
        return 1  # Default to page 1 if not found

    def _extract_datetime_from_path(self, html_file):
        """Extract date and time information from the file path"""
        try:
            # Extract from path structure: search_term/YYYY-MM-DD/HH-MM/search_term_page1_HH-MM-SS.html
            path_parts = html_file.split(os.sep)
            
            # Extract date from directory structure
            for part in path_parts:
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', part)
                if date_match:
                    date_str = date_match.group(1)
                    break
            else:
                date_str = None
                
            # Extract hour-minute from directory structure
            for part in path_parts:
                time_match = re.match(r'(\d{2}-\d{2})', part)
                if time_match and not re.match(r'\d{4}-\d{2}-\d{2}', part):  # Make sure it's not the date
                    hour_minute = time_match.group(1)
                    break
            else:
                hour_minute = None
                
            # Extract seconds from filename
            filename = os.path.basename(html_file)
            seconds_match = re.search(r'_(\d{2}-\d{2}-\d{2})\.html', filename)
            if seconds_match:
                seconds = seconds_match.group(1)
            else:
                seconds = None
                
            return {
                'scrape_date': date_str,
                'scrape_time': f"{hour_minute}:{seconds.split('-')[2]}" if hour_minute and seconds else None,
                'scrape_hour': hour_minute.split('-')[0] if hour_minute else None
            }
        except Exception as e:
            logger.warning(f"Error extracting datetime from path {html_file}: {e}")
            return {'scrape_date': None, 'scrape_time': None, 'scrape_hour': None}

    def _clean_price(self, price_text):
        """Clean and convert price text to float"""
        if not price_text:
            return None
            
        # Remove currency symbols and whitespace
        price_str = re.sub(r'[^\d.,]', '', price_text)
        # Replace comma with dot for decimal separator (European format)
        price_str = price_str.replace(',', '.')
        
        try:
            # Find the first valid number in the string
            number_match = re.search(r'\d+\.\d+|\d+', price_str)
            if number_match:
                return float(number_match.group())
            return None
        except:
            return None

    def _extract_ori_price(self, item):
        """Find orginal price of the product"""
        # Look for the original price with strike through
        original_price = None
        original_price_elements = item.select("span.a-price.a-text-price[data-a-strike='true']")
        for elem in original_price_elements:
            # Try to get the price from the a-offscreen or aria-hidden elements inside
            price_text = None
            offscreen = elem.select_one("span.a-offscreen")
            if offscreen:
                price_text = offscreen.text.strip()
            else:
                aria_hidden = elem.select_one("span[aria-hidden='true']")
                if aria_hidden:
                    price_text = aria_hidden.text.strip()
                
            if price_text:
                original_price = self._clean_price(price_text)
                break
        return original_price
                      
    def _extract_sponsored(self, item):
        """Check if the item is sponsored"""
        try:
            # Look for various sponsored indicators
            sponsored_indicators = [
                "span.puis-label-popover-default",
                "span.s-label-popover-default",
                "span.aok-inline-block.s-sponsored-label-info-icon",
            ]
            
            for indicator in sponsored_indicators:
                if item.select(indicator):
                    return True
                    
            # Check for "Sponsored" text
            if item.find(string=re.compile(r'sponsored', re.I)):
                return True
                
            # Check for data attribute
            if "data-component-type" in item.attrs and "sp-sponsored" in item.attrs["data-component-type"]:
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error checking sponsored status: {e}")
            return False

    def _extract_reviews_and_rating(self, item):
        """Extract review count and rating"""
        try:
            reviews_count = None
            rating = None
            
            # Check for specific review count elements
            review_count_elements = item.select("span.a-size-base.s-underline-text, span.a-size-base.a-color-secondary, a[href*='customerReviews'] span")
            for element in review_count_elements:
                text = element.text.strip()
                # Look for numbers followed by "ratings" or "reviews"
                reviews_match = re.search(r'([\d,.]+)(?:\s+ratings|\s+reviews)?', text, re.I)
                if reviews_match:
                    try:
                        count_text = reviews_match.group(1).replace(',', '').replace('.', '')
                        reviews_count = int(count_text)
                        break  # Found a valid review count
                    except ValueError:
                        continue
            
            # If no review count found, try more generic selectors
            if not reviews_count:
                # Find review link/container
                review_elements = item.select("a[href*='customerReviews'], span.a-size-base.puis-normal-weight-text, div.a-row.a-size-small span.a-size-base")
                
                for element in review_elements:
                    text = element.text.strip()
                    
                    # Extract review count
                    reviews_match = re.search(r'([\d,.]+)(?:\s+ratings|\s+reviews)', text, re.I)
                    if reviews_match:
                        try:
                            reviews_count = int(reviews_match.group(1).replace(',', '').replace('.', ''))
                            break
                        except ValueError:
                            continue
            
            # Extract rating
            rating_elements = item.select("i.a-icon-star, i.a-icon-star-small, span.a-icon-alt")
            for element in rating_elements:
                text = element.text.strip()
                if text:
                    # Direct text like "4.5 out of 5 stars"
                    rating_match = re.search(r'(\d+(?:\.\d+)?)\s+out of\s+\d', text, re.I)
                    if rating_match:
                        rating = float(rating_match.group(1))
                        break
                else:
                    # Try to get from class name
                    class_list = element.get("class", [])
                    for class_name in class_list:
                        rating_match = re.search(r'a-star-([1-5])(?:-\d+)?', class_name)
                        if rating_match:
                            # Check if it's "a-star-4-5" format (4.5 stars)
                            if '-' in rating_match.group(1):
                                parts = rating_match.group(1).split('-')
                                if len(parts) == 2:
                                    try:
                                        rating = float(f"{parts[0]}.{parts[1]}")
                                        break
                                    except ValueError:
                                        pass
                            else:
                                rating = float(rating_match.group(1))
                                break
            
            # If rating not found yet, try the aria-label attribute
            if not rating:
                star_elements = item.select("[aria-label*='stars']")
                for element in star_elements:
                    aria_label = element.get("aria-label", "")
                    rating_match = re.search(r'(\d+(?:\.\d+)?)\s+out of\s+\d+\s+stars', aria_label, re.I)
                    if rating_match:
                        rating = float(rating_match.group(1))
                        break
            
            return reviews_count, rating
        except Exception as e:
            logger.warning(f"Error extracting reviews and rating: {e}")
            return None, None
        
    def _extract_sales_history(self, element):
        """Extract sales history text if available"""
        sales_elements = element.select('span.a-size-base')
        
        for span in sales_elements:
            text = span.text.strip()
            if any(keyword in text.lower() for keyword in ['bought', 'orders', 'purchased']):
                return text
        
        return None

    def _extract_prime(self, item):
        """Check if the item has Prime shipping"""
        try:
            # Look for prime logo/badge
            prime_indicators = [
                "i.a-icon-prime",
                "span.aok-relative span.a-icon-prime",
                "span.a-icon.a-icon-prime"
            ]
            
            for indicator in prime_indicators:
                if item.select(indicator):
                    return True
            
            # Check text mentions
            prime_texts = item.find_all(string=re.compile(r'prime shipping|prime delivery', re.I))
            if prime_texts:
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error checking prime status: {e}")
            return False

    def _extract_asin(self, item):
        """Extract the ASIN from the item"""
        try:
            # Try direct data attribute first
            if "data-asin" in item.attrs:
                asin = item.attrs["data-asin"]
                if asin and len(asin) > 5:  # Basic validation
                    return asin
            
            # Try from data-component-id
            if "data-component-id" in item.attrs:
                comp_id = item.attrs["data-component-id"]
                asin_match = re.search(r'(?:asin|product)/([A-Z0-9]{10})', comp_id)
                if asin_match:
                    return asin_match.group(1)
            
            # Try from links
            for link in item.select("a[href*='/dp/'], a[href*='/gp/product/']"):
                href = link.get("href", "")
                asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|\?|$)', href)
                if asin_match:
                    return asin_match.group(1)
            
            return None
        except Exception as e:
            logger.warning(f"Error extracting ASIN: {e}")
            return None

    def _extract_title(self, item):
        """Extract product title"""
        try:
            # Try specific title elements first
            title_elements = item.select("h2 a span, h5 a span, span.a-size-medium.a-color-base.a-text-normal")
            
            if title_elements:
                return title_elements[0].text.strip()
            
            # Try links with title attribute
            links = item.select("a[title]")
            if links:
                return links[0].get("title", "").strip()
                
            # Try any text in the h2
            h2 = item.select("h2")
            if h2:
                return h2[0].text.strip()
                
            return None
        except Exception as e:
            logger.warning(f"Error extracting title: {e}")
            return None

    def _extract_price(self, item):
        """Extract product price"""
        try:
            # Try all common price selectors
            price_selectors = [
                "span.a-price span.a-offscreen",
                "span.a-price-whole",
                "span.a-color-price",
                "span.a-price"
            ]
            
            for selector in price_selectors:
                elements = item.select(selector)
                if elements:
                    price_text = elements[0].text.strip()
                    return self._clean_price(price_text)
            
            return None
        except Exception as e:
            logger.warning(f"Error extracting price: {e}")
            return None

    def parse_search_html_file(self, html_file):
        """
        Parse a single search results HTML file
        
        Args:
            html_file (str): Path to the HTML file
            
        Returns:
            list: List of dictionaries containing product details
        """
        try:
            logger.info(f"Parsing file: {html_file}")
            
            # Extract metadata from filename and path
            filename = os.path.basename(html_file)
            # Get search term from directory structure - search_term/YYYY-MM-DD/HH-MM/
            directory_path = os.path.dirname(html_file)
            path_parts = directory_path.split(os.sep)
            
            # The search term is the directory at the base level
            # Find the index of the html_dir in the path
            html_dir_index = -1
            for i, part in enumerate(path_parts):
                if part == os.path.basename(self.html_dir):
                    html_dir_index = i
                    break
            
            # The search term directory should be right after the html_dir
            if html_dir_index != -1 and html_dir_index + 1 < len(path_parts):
                safe_term = path_parts[html_dir_index + 1]
                search_term = safe_term.replace('_', ' ').strip()
            else:
                # Fallback to getting search term from filename
                search_term_match = re.match(r'([^_]+)', filename)
                if search_term_match:
                    search_term = search_term_match.group(1).replace('_', ' ').strip()
                else:
                    search_term = "Unknown"
            
            page_number = self._extract_page_number(filename)
            datetime_info = self._extract_datetime_from_path(html_file)
            
            # Read the HTML file
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all search result items
            result_items = soup.select("div[data-component-type='s-search-result']")
            
            if not result_items:
                logger.warning(f"No search results found in {html_file}")
                return []
            
            # Process each search result
            results = []
            for position, item in enumerate(result_items, 1):
                asin = self._extract_asin(item)
                
                if not asin:
                    continue  # Skip items without ASIN
                
                title = self._extract_title(item)
                price = self._extract_price(item)
                original_price = self._extract_ori_price(item)
                is_sponsored = self._extract_sponsored(item)
                reviews_count, rating = self._extract_reviews_and_rating(item)
                sales_history = self._extract_sales_history(item)
                is_prime = self._extract_prime(item)
                
                # Create result object with all required fields
                result = {
                    'asin': asin,
                    'search_term': search_term,
                    'page_number': page_number if page_number else 1,
                    'position': position,
                    'scrape_date': datetime_info.get('scrape_date'),
                    'scrape_time': datetime_info.get('scrape_time'),
                    'scrape_hour': datetime_info.get('scrape_hour'),
                    'title': title,
                    'price': price,
                    'original_price': original_price,
                    'sponsored': is_sponsored,
                    'reviews_count': reviews_count,
                    'rating': rating,
                    'sales_history': sales_history,
                    'prime': is_prime
                }
                
                results.append(result)
            
            logger.info(f"Extracted {len(results)} products from {html_file}")
            return results
            
        except Exception as e:
            logger.error(f"Error parsing file {html_file}: {e}")
            return []

    def parse_search_term_for_run(self, search_term, run_datetime=None):
        """
        Parse HTML files for a specific search term for a specific scheduled run
        
        Args:
            search_term (str): The search term to process
            run_datetime (tuple): Optional (date, hour-minute) to specify a particular run
            
        Returns:
            pandas.DataFrame: DataFrame containing product details for this run
        """
        all_results = []
        
        # Create safe search term for directory lookup
        safe_term = re.sub(r'[^a-zA-Z0-9]', '_', search_term)
        term_dir = os.path.join(self.html_dir, safe_term)
        
        if not os.path.exists(term_dir):
            logger.error(f"Search term directory not found: {term_dir}")
            return pd.DataFrame()
        
        # Find all date directories or use specific date if provided
        if run_datetime and run_datetime[0]:
            date_dirs = [run_datetime[0]] if os.path.exists(os.path.join(term_dir, run_datetime[0])) else []
        else:
            date_dirs = [d for d in os.listdir(term_dir) if os.path.isdir(os.path.join(term_dir, d))]
        
        for date_dir in date_dirs:
            date_path = os.path.join(term_dir, date_dir)
            
            # Find all time directories or use specific time if provided
            if run_datetime and run_datetime[1]:
                time_dirs = [run_datetime[1]] if os.path.exists(os.path.join(date_path, run_datetime[1])) else []
            else:
                time_dirs = [d for d in os.listdir(date_path) if os.path.isdir(os.path.join(date_path, d))]
            
            for time_dir in time_dirs:
                time_path = os.path.join(date_path, time_dir)
                
                # Find all HTML files
                html_files = glob.glob(os.path.join(time_path, "*.html"))
                
                for html_file in html_files:
                    results = self.parse_search_html_file(html_file)
                    all_results.extend(results)
        
        if not all_results:
            logger.warning(f"No results found for search term: {search_term}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_results)
        logger.info(f"Created DataFrame with {len(df)} products for search term: {search_term}")
        
        return df

    def process_all_runs(self):
        """
        Process all search terms and create separate files for each scheduled run
        
        Returns:
            dict: Dictionary mapping run timestamps to DataFrames
        """
        # First, identify all unique runs (date + hour-minute combinations)
        runs = set()
        search_terms = [d for d in os.listdir(self.html_dir) if os.path.isdir(os.path.join(self.html_dir, d))]
        
        for safe_term in search_terms:
            term_dir = os.path.join(self.html_dir, safe_term)
            date_dirs = [d for d in os.listdir(term_dir) if os.path.isdir(os.path.join(term_dir, d))]
            
            for date_dir in date_dirs:
                date_path = os.path.join(term_dir, date_dir)
                time_dirs = [d for d in os.listdir(date_path) if os.path.isdir(os.path.join(date_path, d))]
                
                for time_dir in time_dirs:
                    runs.add((date_dir, time_dir))
        
        logger.info(f"Found {len(runs)} scheduled runs across all search terms")
        
        # Process each run separately
        run_results = {}
        for date_dir, time_dir in sorted(runs):
            run_id = f"{date_dir}_{time_dir}"
            logger.info(f"Processing run: {run_id}")
            
            all_results = []
            for safe_term in search_terms:
                search_term = safe_term.replace('_', ' ').strip()
                df = self.parse_search_term_for_run(search_term, (date_dir, time_dir))
                if not df.empty:
                    all_results.append(df)
            
            if all_results:
                combined_df = pd.concat(all_results, ignore_index=True)
                run_results[run_id] = combined_df
                logger.info(f"Run {run_id}: Collected {len(combined_df)} products across all search terms")
            else:
                logger.warning(f"Run {run_id}: No results found for any search term")
        
        return run_results


def main():
    parser = argparse.ArgumentParser(description="Parse Amazon search results HTML files")
    parser.add_argument("--html-dir", required=True, help="Directory containing the HTML files")
    parser.add_argument("--search-term", help="Specific search term to parse (optional)")
    parser.add_argument("--run-datetime", help="Specific run datetime in format YYYY-MM-DD_HH-MM (optional)")
    parser.add_argument("--output-dir", default="parsed_results_1", help="Directory to save output files")
    parser.add_argument("--single-file", action="store_true", help="Output all results to a single file instead of per-run files")
    
    args = parser.parse_args()
    
    try:
        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)
        
        html_parser = AmazonSearchHTMLParser(args.html_dir)
        
        if args.search_term and args.run_datetime:
            # Parse a specific search term for a specific run
            date_str, time_str = args.run_datetime.split('_')
            logger.info(f"Parsing results for search term '{args.search_term}' from run {args.run_datetime}")
            results_df = html_parser.parse_search_term_for_run(args.search_term, (date_str, time_str))
            
            if not results_df.empty:
                output_file = os.path.join(args.output_dir, f"{args.search_term.replace(' ', '_')}_{args.run_datetime}.csv")
                results_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                logger.info(f"Results saved to {output_file}")
                
        elif args.search_term:
            # Parse all runs for a specific search term
            logger.info(f"Parsing all runs for search term: {args.search_term}")
            results_df = html_parser.parse_search_term_for_run(args.search_term)
            
            if not results_df.empty:
                output_file = os.path.join(args.output_dir, f"{args.search_term.replace(' ', '_')}_all_runs.csv")
                results_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                logger.info(f"Results saved to {output_file}")
                
        elif args.run_datetime:
            # Parse all search terms for a specific run
            date_str, time_str = args.run_datetime.split('_')
            logger.info(f"Parsing all search terms for run: {args.run_datetime}")
            
            all_results = []
            search_terms = [d for d in os.listdir(args.html_dir) if os.path.isdir(os.path.join(args.html_dir, d))]
            
            for safe_term in search_terms:
                search_term = safe_term.replace('_', ' ').strip()
                df = html_parser.parse_search_term_for_run(search_term, (date_str, time_str))
                if not df.empty:
                    all_results.append(df)
            
            if all_results:
                combined_df = pd.concat(all_results, ignore_index=True)
                output_file = os.path.join(args.output_dir, f"all_terms_{args.run_datetime}.csv")
                combined_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                logger.info(f"Results saved to {output_file}")
            else:
                logger.warning(f"No results found for run {args.run_datetime}")
                
        elif args.single_file:
            # Output everything to a single file
            logger.info("Parsing all search terms and runs into a single file")
            
            all_results = []
            for safe_term in os.listdir(args.html_dir):
                if os.path.isdir(os.path.join(args.html_dir, safe_term)):
                    search_term = safe_term.replace('_', ' ').strip()
                    df = html_parser.parse_search_term_for_run(search_term)
                    if not df.empty:
                        all_results.append(df)
            
            if all_results:
                combined_df = pd.concat(all_results, ignore_index=True)
                output_file = os.path.join(args.output_dir, "all_search_results.csv")
                combined_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                logger.info(f"All results saved to {output_file}")
            else:
                logger.warning("No results found in any search term directory")
                
        else:
            # Process each run separately
            logger.info("Processing all search terms organized by scheduled runs")
            run_results = html_parser.process_all_runs()
            
            if run_results:
                for run_id, df in run_results.items():
                    output_file = os.path.join(args.output_dir, f"run_{run_id}.csv")
                    df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    logger.info(f"Results for run {run_id} saved to {output_file}")
                    
                    # Also save to JSON if needed
                    json_output = os.path.join(args.output_dir, f"run_{run_id}.json")
                    df.to_json(json_output, orient='records', lines=True)
                    logger.info(f"Results for run {run_id} also saved to {json_output}")
            else:
                logger.warning("No results found for any run")
    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()