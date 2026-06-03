import fs from 'fs';
import path from 'path';

const BUDGET_FILE = path.resolve('data/budget.json');

function loadBudget() {
  try {
    const raw = fs.readFileSync(BUDGET_FILE, 'utf8');
    const data = JSON.parse(raw);
    const today = new Date().toISOString().slice(0, 10);
    if (data.date !== today) return { date: today, spent: 0 };
    return data;
  } catch {
    return { date: new Date().toISOString().slice(0, 10), spent: 0 };
  }
}

function saveBudget(data) {
  const dir = path.dirname(BUDGET_FILE);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = `${BUDGET_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, BUDGET_FILE);
}

export function recordCost(amount) {
  const budget = loadBudget();
  budget.spent += amount;
  saveBudget(budget);

  const cap = parseFloat(process.env.DAILY_COST_CAP_USD || '2.00');
  const alert = parseFloat(process.env.ALERT_COST_THRESHOLD_USD || '1.50');

  if (budget.spent >= alert) {
    console.error(`[BUDGET ALERT] Daily spend $${budget.spent.toFixed(4)} exceeds alert threshold $${alert}`);
  }

  if (budget.spent >= cap) {
    throw new Error(`Daily cost cap $${cap} reached (spent: $${budget.spent.toFixed(4)}). Pipeline halted.`);
  }

  return budget.spent;
}

export function getDailySpend() {
  return loadBudget().spent;
}

export function canAffordDalle() {
  const budget = loadBudget();
  const cap = parseFloat(process.env.DAILY_COST_CAP_USD || '2.00');
  const cost = parseFloat(process.env.DALLE_COST_PER_IMAGE || '0.04');
  return budget.spent + cost < cap;
}
