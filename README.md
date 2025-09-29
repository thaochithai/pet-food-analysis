# 🐾 Pet Food Product Analysis on Amazon  

## Project Overview  
This project analyzes the **pet food, treats, and health supplies** market on Amazon to uncover **brand positioning, pricing strategies, consumer preferences, and product performance**.  

Data was collected from the **first 10 result pages of targeted Amazon search queries** (e.g., *dog food, cat food, pet treats, health supplies*) and analyzed using **Python** (`pandas`, `seaborn`, `matplotlib`, `wordcloud`).  

The goal is to deliver **market intelligence insights** that inform **brand competitiveness, product assortment strategy, and pricing decisions**.  

---

## Methodology  

### Data Collection  
- Scraped structured product data including:  
  - **Attributes**: title, brand, category hierarchy, pricing (absolute & per-unit), customer ratings, review counts  
  - **Performance metrics**: Bestseller rank, 30-day sales velocity, sponsored listing flag  
  - **Content elements**: bullet points, product descriptions, usage claims, special ingredients  

### Data Processing  
- **Cleaning**: handled missing reviews/ratings, standardized categorical attributes  
- **Feature engineering**: derived `price_per_unit`, normalized text for NLP (lemmatization, stopword removal)  
- **Analysis tools**:  
  - `pandas` (data manipulation)  
  - `seaborn` & `matplotlib` (visualizations)  
  - `wordcloud` (text mining for claims & ingredients)  

---

## Key Insights  

### 1. Brand Performance  
- **Felix** leads in efficiency, averaging **71 units sold per product in 30 days**, with its *Delicious Duo Maxi Pack* exceeding **1K units sold in the past month**.  
- **Pedigree, Whiskas, Sheba, Royal Canin** dominate by product count, but performance per listing varies.  
- **Average rating leaders**: Purina (4.6) and Felix (4.5+), while **Edgard & Cooper** lags at 4.3.  

<img width="600" height="400" src="https://github.com/user-attachments/assets/695de523-f137-4879-b1fd-d1783d1b6c90" />  
<img width="600" height="400"  src="https://github.com/user-attachments/assets/d07ed59b-86c6-4093-a51d-06e69bb50ab2" />  

---

### 2. Pricing Strategy & Market Segmentation  

#### Sub-Category Price Differentiation  
- **Food**: value-driven (€39.13/unit avg.)  
- **Health Supplies**: mid-premium (€129.73/unit)  
- **Treats**: highest-priced segment (€222.05/unit)  

<img width="500" height="400" src="https://github.com/user-attachments/assets/65c729de-d75c-4c91-81ab-e04ef6b459f7" />  

#### Brand Premium Positioning  
- **Royal Canin**: consistent premium pricing across categories  
- **Purina**: strong premium presence in health supplies  
- **Pedigree**: premium strategy in treats  

<img width="500" height="400" src="https://github.com/user-attachments/assets/efc4e514-8e98-43b5-959e-106c2abe4e58" />  

#### Flavor-Based Price Elasticity  
- **Chicken** dominates in volume (most listed) but is low-priced (€33.43).  
- **Beef (€53.90)** and **unclassified flavors (€153.50)** carry premium pricing.  
- Suggests **flavor innovation** could unlock margin opportunities.  

<img width="500" height="400" src="https://github.com/user-attachments/assets/8f8a32ce-5866-441b-8eb9-91ed2d1c16c0" />  

**Strategic implication**: Diversifying beyond chicken into niche flavors offers potential for premium positioning.  

---

### 3. Product Characteristics  

- **Top Flavors**: Chicken, Beef, Salmon, Lamb  
- **Popular ingredients**: turkey, fish oil, fatty acids, prebiotics → signaling **nutrition & natural health** focus  
<img width="790" height="425" src="https://github.com/user-attachments/assets/9293129f-e832-4a65-b132-e768955c2117" />  

- **Usage claims**: skin & coat health, sensitive stomach, immune support → health-driven narratives dominate competitive differentiation  
<img width="790" height="425" src="https://github.com/user-attachments/assets/6f26ffe9-2b45-4174-a849-0ba875e0113b" />  

---

## Next Steps  
- Track ranking & sales performance over time (longitudinal analysis)  
- Segment brands into **value vs. premium clusters**  
- Perform **sentiment analysis** of reviews for deeper brand insights  
- Build **predictive models** to identify sales drivers  

---
## Takeaway  
**Premium pricing, health-driven claims, and flavor innovation** emerge as the strongest levers for competitive advantage.  

---
