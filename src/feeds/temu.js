import { logger } from '../utils/logger.js';

// Deal themes give the AI variety to generate different posts each run
const THEMES = [
  { name: 'Electronics & Gadgets',     description: 'Smartphones, earbuds, smart home devices and tech accessories at unbeatable prices.', category: 'Electronics' },
  { name: 'Fashion & Clothing',         description: 'Trendy clothing, shoes and accessories for men, women and kids.',                     category: 'Fashion' },
  { name: 'Home & Kitchen',             description: 'Kitchen gadgets, storage solutions, decor and everything you need for the home.',     category: 'Home' },
  { name: 'Beauty & Personal Care',     description: 'Skincare, makeup, hair care and personal care products at a fraction of retail price.',  category: 'Beauty' },
  { name: 'Sports & Outdoors',          description: 'Fitness equipment, outdoor gear, sportswear and accessories for an active lifestyle.', category: 'Sports' },
  { name: 'Toys & Kids',                description: 'Educational toys, games and fun products for babies, toddlers and kids of all ages.',  category: 'Toys' },
  { name: 'Tools & Home Improvement',   description: 'Power tools, hand tools, garden equipment and DIY supplies.',                         category: 'Tools' },
  { name: 'Jewellery & Accessories',    description: 'Earrings, necklaces, rings, watches and bags at incredible prices.',                  category: 'Jewellery' },
  { name: 'Pet Supplies',               description: 'Food, toys, grooming tools and accessories for cats, dogs and all pets.',             category: 'Pets' },
  { name: 'Office & Stationery',        description: 'Desk organisers, stationery, printer supplies and home-office essentials.',           category: 'Office' },
  { name: 'Baby & Maternity',           description: 'Baby gear, clothing, feeding essentials and nursery decor.',                          category: 'Baby' },
  { name: 'Automotive & Accessories',   description: 'Car accessories, cleaning supplies, gadgets and parts at amazing prices.',            category: 'Automotive' },
  { name: 'Garden & Outdoor Living',    description: 'Plants, garden tools, outdoor furniture and everything to beautify your space.',      category: 'Garden' },
  { name: 'Health & Wellness',          description: 'Supplements, fitness accessories, massage tools and wellness products.',              category: 'Health' },
  { name: 'Arts & Crafts',              description: 'Art supplies, craft kits, sewing materials and creative tools.',                      category: 'Arts' },
];

// Seasonal themes weighted by current month for timely content
const SEASONAL_THEMES = {
  // month index 0=Jan
  0:  { name: 'New Year Deals',       description: 'Start the new year right with incredible deals on everything you need.', category: 'Seasonal' },
  1:  { name: "Valentine's Gifts",    description: "Find the perfect gift for Valentine's Day — jewellery, beauty, and more.", category: 'Gifts' },
  2:  { name: 'Spring Refresh',       description: 'Spring clean and refresh your home, wardrobe and garden at amazing prices.', category: 'Seasonal' },
  3:  { name: 'Spring Fashion',       description: 'New season, new style — fresh spring clothing and accessories now in stock.', category: 'Fashion' },
  4:  { name: "Mother's Day Gifts",   description: "Treat mum to something special — beauty, home, jewellery and more.", category: 'Gifts' },
  5:  { name: 'Summer Essentials',    description: 'Everything you need for summer — swimwear, outdoor gear and travel accessories.', category: 'Seasonal' },
  6:  { name: 'Summer Sale',          description: 'Massive summer clearance — huge discounts on fashion, electronics and home.', category: 'Sale' },
  7:  { name: 'Back to School',       description: 'Back-to-school season — stationery, bags, electronics and study essentials.', category: 'Education' },
  8:  { name: 'Autumn Picks',         description: 'Cosy autumn essentials — knitwear, home decor and seasonal must-haves.', category: 'Seasonal' },
  9:  { name: 'Halloween Deals',      description: 'Spooky savings on costumes, decorations and party supplies.', category: 'Seasonal' },
  10: { name: 'Black Friday Preview', description: 'Early Black Friday deals — electronics, fashion and home at massive discounts.', category: 'Sale' },
  11: { name: 'Christmas Gifts',      description: 'Find the perfect Christmas gift for everyone on your list.', category: 'Gifts' },
};

function pickTheme() {
  const month = new Date().getMonth();
  // 30% chance of seasonal theme to keep content timely
  if (Math.random() < 0.3 && SEASONAL_THEMES[month]) return SEASONAL_THEMES[month];
  return THEMES[Math.floor(Math.random() * THEMES.length)];
}

export async function getTemuProduct() {
  const urls = [
    process.env.TEMU_AFFILIATE_URL_1,
    process.env.TEMU_AFFILIATE_URL_2,
    process.env.TEMU_AFFILIATE_URL_3,
  ].filter(Boolean);

  if (urls.length === 0) return null;

  const baseUrl  = urls[Math.floor(Math.random() * urls.length)];
  const theme    = pickTheme();
  const tag      = `${theme.category.toLowerCase()}-${Date.now()}`;
  // Append a unique sub-ID so each post gets its own dedup key
  const sep      = baseUrl.includes('?') ? '&' : '?';
  const affiliateUrl = `${baseUrl}${sep}sub=${tag}`;

  logger.info(`Temu theme selected: "${theme.name}"`);

  return {
    id:             `temu-${tag}`,
    name:           `Temu ${theme.name} Deals`,
    description:    theme.description,
    siteUrl:        affiliateUrl,
    imageUrl:       null,
    price:          null,
    currency:       'USD',
    commissionRate: 0,
    category:       theme.category,
    source:         'temu',
  };
}
