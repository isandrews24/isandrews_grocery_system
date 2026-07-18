"""Seed demo data: users, categories, products, inventory, reviews.

Run with: python seed_data.py
"""
import random
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models import User, Category, Product, Inventory, Location, Review

DEMO_PASSWORD = "ChangeMe123!"

CATEGORY_COLORS = {
    "Beverages": "2c4270",
    "Bakery": "b8860b",
    "Produce": "1c8a52",
    "Staples": "d4a017",
    "Spices & Seasoning": "c0392b",
    "Dairy & Eggs": "6b7280",
    "Canned & Frozen": "1b2a4a",
    "Oils": "8a5a12",
    "Snacks": "993556",
}


def placeholder_image(name, category):
    color = CATEGORY_COLORS.get(category, "5c6b85")
    return f"https://placehold.co/400x400/{color}/ffffff?text={quote(name)}&font=poppins"


# Real, freely-licensed photos (Wikimedia Commons: CC0 / CC-BY / CC-BY-SA / public
# domain) keyed by SKU. Deliberately generic/type-level rather than actual branded
# packaging, since brand product photography is copyrighted - these are genuine
# photos of the kind of item, sourced from a repository built for free reuse.
PRODUCT_IMAGES = {
    "BEV-001": "https://upload.wikimedia.org/wikipedia/commons/a/aa/IBC_root_beer_%283073572730%29.jpg",
    "BEV-002": "https://upload.wikimedia.org/wikipedia/commons/4/44/Home_water_filters%2C_water_purifiers%2C_and_bottled_water_in_India.jpg",
    "BEV-003": "https://upload.wikimedia.org/wikipedia/commons/a/a0/Zobo%28hibiscus%29_drink.jpg",
    "BEV-004": "https://upload.wikimedia.org/wikipedia/commons/3/30/Fruit_juice_sold_in_Hong_Kong.jpg",
    "BEV-005": "https://upload.wikimedia.org/wikipedia/commons/a/af/Kangso_Mineral_Water_Bottling_Factory_-_06.jpg",
    "BEV-006": "https://upload.wikimedia.org/wikipedia/commons/2/23/Chocolate_milk.JPG",
    "BAK-001": "https://upload.wikimedia.org/wikipedia/commons/9/9f/Fatayer.jpg",
    "BAK-002": "https://upload.wikimedia.org/wikipedia/commons/5/5e/Fresh_Scali_bread_loaf_from_Winter_Hill_Bakery.jpg",
    "BAK-003": "https://upload.wikimedia.org/wikipedia/commons/3/33/Fresh_made_bread_05.jpg",
    "BAK-004": "https://upload.wikimedia.org/wikipedia/commons/b/bb/Panettone_aufgeschnitten_freigestellt.jpg",
    "BAK-005": "https://upload.wikimedia.org/wikipedia/commons/e/ea/Doughnut_2.jpg",
    "PRO-001": "https://upload.wikimedia.org/wikipedia/commons/c/c3/Organic_home-grown_tomatoes_-_unripe_to_ripe.jpg",
    "PRO-002": "https://upload.wikimedia.org/wikipedia/commons/7/74/Indian_Onion.jpg",
    "PRO-003": "https://upload.wikimedia.org/wikipedia/commons/b/b3/African_eggplant_also_known_as_garden_eggs_02.jpg",
    "PRO-004": "https://upload.wikimedia.org/wikipedia/commons/2/26/Okra_%28Abelmoschus_esculentus%29_Feb_2019._DSC_0060_01.jpg",
    "PRO-005": "https://upload.wikimedia.org/wikipedia/commons/7/7c/An_entire_cluster_of_plantains.jpg",
    "PRO-006": "https://upload.wikimedia.org/wikipedia/commons/c/cc/Plantain_-_raw_banana.jpg",
    "PRO-007": "https://upload.wikimedia.org/wikipedia/commons/6/6b/A_Farmer_Harvesting_Cassava_Root_2.jpg",
    "PRO-008": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Yam_Tubers_stacked_on_a_plastic_table_03.jpg",
    "PRO-009": "https://upload.wikimedia.org/wikipedia/commons/2/2b/Colocasia_esculenta_15zz.jpg",
    "PRO-010": "https://upload.wikimedia.org/wikipedia/commons/9/99/GingerRoot_Novo_Los_Angeles.jpg",
    "PRO-011": "https://upload.wikimedia.org/wikipedia/commons/1/1d/Capsicum_chinense_Scotch_Bonnet_2zz.jpg",
    "STA-001": "https://upload.wikimedia.org/wikipedia/commons/f/fa/Ghana_Jollof_Rice_with_Chicken.jpg",
    "STA-002": "https://upload.wikimedia.org/wikipedia/commons/1/13/Cassava_Flakes_%28garri%29.jpg",
    "STA-003": "https://upload.wikimedia.org/wikipedia/commons/c/ce/Plain_white_rice-min-min.jpg",
    "STA-004": "https://upload.wikimedia.org/wikipedia/commons/d/d0/BlackEyedPeas.JPG",
    "STA-005": "https://upload.wikimedia.org/wikipedia/commons/d/d1/Calabash_bowls_-_6_hand_processing_millet_flour%2C_millet_pellets_vs_millet_flour.jpg",
    "STA-006": "https://upload.wikimedia.org/wikipedia/commons/6/64/A_cassava_flour_seller.jpg",
    "STA-007": "https://upload.wikimedia.org/wikipedia/commons/0/0a/Conkie.jpg",
    "SPI-001": "https://upload.wikimedia.org/wikipedia/commons/7/76/Pepper_Sauce_Bottling_%2850559002081%29.jpg",
    "SPI-002": "https://upload.wikimedia.org/wikipedia/commons/7/7f/Spice_vendor_in_Yaounde_market.jpg",
    "SPI-003": "https://upload.wikimedia.org/wikipedia/commons/7/79/Bouillon_cube.jpg",
    "SPI-004": "https://upload.wikimedia.org/wikipedia/commons/9/94/Ginger_Garlic_Paste.jpg",
    "SPI-005": "https://upload.wikimedia.org/wikipedia/commons/7/70/Curry_powder.jpg",
    "DAI-001": "https://upload.wikimedia.org/wikipedia/commons/8/8b/PowderedMilk.jpg",
    "DAI-002": "https://upload.wikimedia.org/wikipedia/commons/c/cc/Condensed_and_evaporated_milk.jpg",
    "DAI-003": "https://upload.wikimedia.org/wikipedia/commons/4/4c/Egg_cartons_with_chicken_eggs_02.jpg",
    "DAI-004": "https://upload.wikimedia.org/wikipedia/commons/f/fb/Llaeth_y_Llan%2C_Village_Dairy_yogurt.jpg",
    "CAN-001": "https://upload.wikimedia.org/wikipedia/commons/e/ee/16-07-2017_Can_of_Sardines%2C_Alva%2C_Portugal.JPG",
    "CAN-002": "https://upload.wikimedia.org/wikipedia/commons/3/31/20250817_can_mackerel_fillets.jpg",
    "CAN-003": "https://upload.wikimedia.org/wikipedia/commons/8/86/Chambo_%28tilapia%29_fish%2C_Blantyre_market%2C_Malawi.jpg",
    "CAN-004": "https://upload.wikimedia.org/wikipedia/commons/a/ae/FoodMeat.jpg",
    "OIL-001": "https://upload.wikimedia.org/wikipedia/commons/3/33/Bottle_1_liter_Sunflower_refined_oil.jpg",
    "OIL-002": "https://upload.wikimedia.org/wikipedia/commons/b/ba/Palm_oil_in_a_white_bowl.jpg",
    "OIL-003": "https://upload.wikimedia.org/wikipedia/commons/1/1f/HK_SYP_%E8%A5%BF%E7%87%9F%E7%9B%A4_Sai_Ying_Pun_%E7%AC%AC%E4%B8%89%E8%A1%97_43_Third_Street_%E6%9D%B1%E5%8D%97%E5%A4%A7%E5%BB%88_Tong_Nam_Mansion_%E4%BD%B3%E5%AF%B6%E9%A3%9F%E5%93%81_Kai_Bo_Food_Supermarket_cooking_oil_bottles_n_rice_bags_August_2022_Px3.jpg",
    "SNK-001": "https://upload.wikimedia.org/wikipedia/commons/5/5f/Green_and_Black%27s_dark_chocolate_bar_1.jpg",
    "SNK-002": "https://upload.wikimedia.org/wikipedia/commons/f/f4/Peanuts_with_gourd_scoop_in_wood_bowl.jpg",
    "SNK-003": "https://upload.wikimedia.org/wikipedia/commons/c/ce/PLANTAIN_CHIPS.jpg",
    "SNK-004": "https://upload.wikimedia.org/wikipedia/commons/a/a6/The_Process_of_Chin-chin_making.jpg",
}


def product_image(sku, name, category):
    return PRODUCT_IMAGES.get(sku) or placeholder_image(name, category)


app = create_app()

with app.app_context():
    db.create_all()

    main_store = Location.query.filter_by(is_default=True).first()
    if not main_store:
        main_store = Location(name="Main Store", is_default=True)
        db.session.add(main_store)
        db.session.flush()

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@isandrewsgrocery.gh", role="superadmin", full_name="Store Admin")
        admin.set_password(DEMO_PASSWORD)
        db.session.add(admin)

    if not User.query.filter_by(username="cashier1").first():
        cashier = User(username="cashier1", email="cashier1@isandrewsgrocery.gh", role="cashier", full_name="Ama Mensah")
        cashier.set_password(DEMO_PASSWORD)
        db.session.add(cashier)

    db.session.commit()

    categories = {}
    for name in CATEGORY_COLORS:
        cat = Category.query.filter_by(name=name).first()
        if not cat:
            cat = Category(name=name)
            db.session.add(cat)
            db.session.flush()
        categories[name] = cat

    db.session.commit()

    # (name, category, sku, price GHS, stock qty, description)
    products = [
        # Beverages
        ("Malt Drink 330ml", "Beverages", "BEV-001", 8.50, 100,
         "A rich, non-alcoholic malt beverage packed with vitamins B1, B2 and B6. Served ice-cold, it's a favourite breakfast and anytime drink across Ghana."),
        ("Bottled Water 750ml", "Beverages", "BEV-002", 3.00, 200,
         "Purified, sealed drinking water sourced and bottled locally. A everyday essential for home, office and on the go."),
        ("Sobolo Drink 500ml", "Beverages", "BEV-003", 6.00, 80,
         "Hibiscus (sorrel) drink brewed with ginger, cloves and a touch of pineapple. Naturally refreshing and rich in antioxidants."),
        ("Kalyppo Juice 350ml", "Beverages", "BEV-004", 4.50, 120,
         "A sweet, fruit-flavoured juice drink loved by kids and adults alike. Comes chilled and ready to enjoy."),
        ("Voltic Water 1.5L", "Beverages", "BEV-005", 5.50, 90,
         "Ghana's leading bottled water brand, sourced from a protected spring and treated to strict quality standards."),
        ("Milo Ready-to-Drink 180ml", "Beverages", "BEV-006", 5.00, 100,
         "The classic chocolate malt drink in a convenient ready-to-drink tetra pack - no mixing required."),
        # Bakery
        ("Meat Pie", "Bakery", "BAK-001", 7.50, 40,
         "Flaky pastry parcel filled with seasoned minced meat, baked fresh daily in-store. Best enjoyed warm."),
        ("Sugar Bread Loaf", "Bakery", "BAK-002", 12.00, 30,
         "Soft, lightly sweetened white bread loaf, a breakfast table staple across Ghanaian households."),
        ("Tea Bread Loaf", "Bakery", "BAK-003", 11.00, 25,
         "A milder, everyday loaf that pairs perfectly with tea, Milo, or a smear of margarine."),
        ("Butter Bread Loaf", "Bakery", "BAK-004", 13.50, 20,
         "Enriched with real butter for a soft crumb and rich flavour - a step up from the everyday loaf."),
        ("Doughnuts (Pack of 6)", "Bakery", "BAK-005", 9.00, 35,
         "Golden, deep-fried dough balls lightly sugared on the outside. A popular street-side and breakfast treat."),
        # Produce
        ("Tomatoes 1kg", "Produce", "PRO-001", 15.00, 60,
         "Fresh, ripe tomatoes ideal for stews, soups and jollof rice base. Sourced from local farms."),
        ("Onions 1kg", "Produce", "PRO-002", 10.00, 60,
         "Firm, everyday cooking onions - the foundation of almost every Ghanaian stew and soup."),
        ("Garden Eggs 1kg", "Produce", "PRO-003", 8.00, 45,
         "Small, slightly bitter white-and-purple garden eggs, delicious roasted, stewed, or in garden egg dip (nkatenkwan-style)."),
        ("Okra 500g", "Produce", "PRO-004", 6.50, 50,
         "Fresh green okra, perfect for the classic Ghanaian okra soup or as a stew thickener."),
        ("Ripe Plantain (Bunch)", "Produce", "PRO-005", 18.00, 40,
         "Sweet, yellow ripe plantain - ideal for frying into kelewele or plantain chips."),
        ("Unripe Plantain (Bunch)", "Produce", "PRO-006", 16.00, 40,
         "Firm green plantain, best for ampesi, roasting, or boiling with stew."),
        ("Cassava 1kg", "Produce", "PRO-007", 7.00, 55,
         "Fresh cassava tuber, a staple root vegetable used for fufu, gari, and boiled ampesi."),
        ("Yam (Tuber)", "Produce", "PRO-008", 20.00, 30,
         "Hearty white yam tuber, excellent boiled, roasted, or pounded into fufu."),
        ("Kontomire (Cocoyam Leaves)", "Produce", "PRO-009", 5.00, 35,
         "Fresh cocoyam leaves used to prepare the classic kontomire stew (palaver sauce)."),
        ("Ginger 250g", "Produce", "PRO-010", 6.00, 50,
         "Aromatic fresh ginger root - essential for sobolo, marinades and everyday cooking."),
        ("Scotch Bonnet Pepper 500g", "Produce", "PRO-011", 9.50, 45,
         "Fiery, fruity scotch bonnet peppers - the heart of Ghanaian pepper sauce and shito."),
        # Staples
        ("Jollof Rice Pack", "Staples", "STA-001", 35.00, 25,
         "Ready-seasoned rice pack for making authentic smoky Ghanaian jollof at home, just add stock and tomato base."),
        ("Gari 1kg", "Staples", "STA-002", 9.00, 4,
         "Toasted, granulated cassava flakes - a pantry essential for gari soakings, gari fortor, or eba."),
        ("Perfumed Rice 5kg", "Staples", "STA-003", 65.00, 30,
         "Long-grain aromatic rice, perfect for jollof, fried rice, or plain boiled rice."),
        ("Waakye Beans Mix 1kg", "Staples", "STA-004", 22.00, 28,
         "Pre-mixed rice and beans with dried waakye leaves for that authentic reddish-brown waakye colour."),
        ("Tuo Zaafi Flour 1kg", "Staples", "STA-005", 18.00, 20,
         "Ground TZ flour for preparing the northern Ghanaian staple, best served with ayoyo or okra soup."),
        ("Fufu Flour 1kg", "Staples", "STA-006", 16.00, 25,
         "Instant fufu flour blend - just add hot water and stir for smooth, stretchy fufu without pounding."),
        ("Banku Mix 1kg", "Staples", "STA-007", 14.00, 22,
         "Fermented corn and cassava dough mix for quick homemade banku, perfect with okra soup or grilled tilapia."),
        # Spices & Seasoning
        ("Shito (Hot Pepper Sauce)", "Spices & Seasoning", "SPI-001", 12.00, 40,
         "Ghana's beloved black pepper sauce made with dried fish, shrimp and chilli - great with waakye, rice, or bread."),
        ("Kelewele Spice Mix", "Spices & Seasoning", "SPI-002", 8.00, 35,
         "A ready-mixed blend of ginger, pepper and warm spices for perfectly seasoned fried plantain (kelewele)."),
        ("Maggi Seasoning Cubes (Pack)", "Spices & Seasoning", "SPI-003", 6.50, 100,
         "The everyday flavour cube found in almost every Ghanaian kitchen, for soups, stews and sauces."),
        ("Ginger Garlic Paste 200g", "Spices & Seasoning", "SPI-004", 9.00, 30,
         "Convenient blended ginger and garlic paste that saves prep time without sacrificing flavour."),
        ("Curry Powder 100g", "Spices & Seasoning", "SPI-005", 7.00, 40,
         "A warm, earthy curry blend for curries, stews, and spiced rice dishes."),
        # Dairy & Eggs
        ("Peak Milk Powder 400g", "Dairy & Eggs", "DAI-001", 28.00, 50,
         "Full-cream powdered milk, a household name in Ghana for tea, porridge and baking."),
        ("Ideal Evaporated Milk 170g", "Dairy & Eggs", "DAI-002", 6.00, 80,
         "Creamy evaporated milk in a tin, perfect for enriching tea, coffee and desserts."),
        ("Fresh Eggs (Crate of 30)", "Dairy & Eggs", "DAI-003", 45.00, 20,
         "Farm-fresh eggs supplied in a full crate of 30, ideal for households and small food businesses."),
        ("Plain Yogurt 500ml", "Dairy & Eggs", "DAI-004", 14.00, 30,
         "Smooth, lightly tangy plain yogurt - great on its own, with fruit, or blended into smoothies."),
        # Canned & Frozen
        ("Titus Sardine (Tin)", "Canned & Frozen", "CAN-001", 8.50, 60,
         "Tinned sardines in rich tomato sauce - a quick protein source for stews, sandwiches or a light meal."),
        ("Geisha Mackerel (Tin)", "Canned & Frozen", "CAN-002", 9.00, 60,
         "Tinned mackerel fillets, a pantry staple for quick fish stew or shito-based dishes."),
        ("Frozen Tilapia 1kg", "Canned & Frozen", "CAN-003", 32.00, 25,
         "Whole frozen tilapia, cleaned and ready for grilling, frying, or light soup."),
        ("Frozen Chicken 1kg", "Canned & Frozen", "CAN-004", 38.00, 25,
         "Fresh-frozen chicken cuts, versatile for grilling, frying or stewing."),
        # Oils
        ("Frytol Cooking Oil 1L", "Oils", "OIL-001", 24.00, 40,
         "Ghana's trusted vegetable cooking oil, suited for frying and everyday cooking."),
        ("Palm Oil 1L", "Oils", "OIL-002", 20.00, 35,
         "Traditional red palm oil, essential for authentic palm nut soup, red-red and local stews."),
        ("Groundnut Oil 1L", "Oils", "OIL-003", 26.00, 30,
         "Light, nutty groundnut oil, great for frying and for groundnut soup preparation."),
        # Snacks
        ("Golden Tree Chocolate Bar", "Snacks", "SNK-001", 10.00, 50,
         "Smooth Ghanaian cocoa chocolate bar, made from locally grown cocoa beans."),
        ("Roasted Groundnuts 250g", "Snacks", "SNK-002", 6.00, 60,
         "Crunchy roasted peanuts, a favourite grab-and-go snack across Ghana."),
        ("Plantain Chips 150g", "Snacks", "SNK-003", 6.50, 50,
         "Thinly sliced, crisply fried plantain chips - lightly salted and perfectly crunchy."),
        ("Chin Chin 250g", "Snacks", "SNK-004", 7.50, 45,
         "Sweet, crunchy fried dough bites, a popular party and everyday snack."),
    ]

    REVIEWER_NAMES = [
        "Ama Owusu", "Kwame Boateng", "Efua Mensah", "Kojo Asante", "Abena Darko",
        "Yaw Appiah", "Akosua Frimpong", "Kwabena Osei", "Adjoa Sarpong", "Kwesi Tetteh",
    ]
    SAMPLE_COMMENTS = {
        5: ["Excellent quality, will buy again!", "Exactly as described, very fresh.", "My family loves this, top quality."],
        4: ["Good product, fair price.", "Solid quality, delivery was quick.", "Would recommend to others."],
        3: ["Decent, does the job.", "Okay for the price.", "Nothing special but fine."],
    }

    random.seed(42)

    for name, cat_name, sku, price, qty, description in products:
        product = Product.query.filter_by(sku=sku).first()
        if not product:
            product = Product(
                sku=sku,
                name=name,
                description=description,
                category_id=categories[cat_name].id,
                barcode_number="20" + sku.replace("-", "").ljust(11, "0"),
                unit_price=price,
                cost_price=round(price * 0.65, 2),
                tax_rate=15.0,
                is_taxable=True,
                unit_of_measure="each",
                image_url=product_image(sku, name, cat_name),
            )
            db.session.add(product)
            db.session.flush()
            db.session.add(Inventory(
                product_id=product.id, location_id=main_store.id,
                quantity_on_hand=qty, reorder_level=5, reorder_quantity=30,
            ))

            # About 60% of products start with a couple of demo reviews
            if random.random() < 0.6:
                for _ in range(random.randint(1, 3)):
                    rating = random.choice([3, 4, 4, 5, 5, 5])
                    db.session.add(Review(
                        product_id=product.id,
                        reviewer_name=random.choice(REVIEWER_NAMES),
                        rating=rating,
                        comment=random.choice(SAMPLE_COMMENTS[rating]),
                    ))

    db.session.commit()
    print(f"Seed complete. {len(products)} products loaded. Login as admin/cashier1 with password:", DEMO_PASSWORD)
