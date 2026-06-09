/**
 * Unit tests for src/utils/schedule-manager.js
 * Run: node --test tests/e2e/schedule-manager.test.js
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildScheduleTimes,
  buildCronExpressions,
  analyzeEngagementByHour,
  suggestBestTimes,
} from '../../src/utils/schedule-manager.js';

describe('buildScheduleTimes', () => {
  test('1 post/day at 8-22 starts at 08:00', () => {
    const [t] = buildScheduleTimes(1, '8-22');
    assert.equal(t.hour, 8); assert.equal(t.minute, 0);
  });

  test('2 posts/day at 8-22 → 08:00 and 15:00', () => {
    const [a, b] = buildScheduleTimes(2, '8-22');
    assert.equal(a.hour, 8);  assert.equal(a.minute, 0);
    assert.equal(b.hour, 15); assert.equal(b.minute, 0);
  });

  test('3 posts returns 3 items', () => {
    assert.equal(buildScheduleTimes(3, '8-22').length, 3);
  });

  test('clamps to min 1', () => {
    assert.equal(buildScheduleTimes(0, '8-22').length, 1);
  });

  test('clamps to max 24', () => {
    assert.equal(buildScheduleTimes(100, '8-22').length, 24);
  });

  test('all hours 0-23', () => {
    for (const t of buildScheduleTimes(6, '0-23')) {
      assert.ok(t.hour >= 0 && t.hour < 24);
    }
  });

  test('all minutes 0-59', () => {
    for (const t of buildScheduleTimes(7, '6-20')) {
      assert.ok(t.minute >= 0 && t.minute < 60);
    }
  });

  test('malformed window falls back gracefully', () => {
    const [t] = buildScheduleTimes(1, 'bad');
    assert.equal(t.hour, 9);
  });
});

describe('buildCronExpressions', () => {
  test('returns 5-part cron strings', () => {
    for (const e of buildCronExpressions(3, '9-21')) {
      assert.equal(e.split(' ').length, 5);
    }
  });

  test('1 post/day → 1 expression', () => {
    assert.equal(buildCronExpressions(1, '10-22').length, 1);
  });

  test('trailing fields are wildcards', () => {
    for (const e of buildCronExpressions(2, '8-20')) {
      assert.ok(e.endsWith('* * *'));
    }
  });
});

describe('analyzeEngagementByHour', () => {
  test('always returns 24 elements', () => {
    assert.equal(analyzeEngagementByHour([]).length, 24);
  });

  test('hours indexed 0-23', () => {
    const data = analyzeEngagementByHour([]);
    for (let i = 0; i < 24; i++) assert.equal(data[i].hour, i);
  });

  test('aggregates engagement correctly', () => {
    const runs = [
      { success: true, timestamp: '2024-01-01T09:00:00Z', likes: 10, reposts: 2, clicks: 0 },
      { success: true, timestamp: '2024-01-02T09:00:00Z', likes: 4,  reposts: 1, clicks: 1 },
    ];
    // h9 score = (10*2+2*3) + (4*2+1*3+1*5) = 26+16 = 42, avg = 21
    const h9 = analyzeEngagementByHour(runs).find(d => d.hour === 9);
    assert.equal(h9.count,    2);
    assert.equal(h9.avgScore, 21);
  });

  test('skips failed runs', () => {
    const data = analyzeEngagementByHour([{ success: false, timestamp: '2024-01-01T10:00:00Z', likes: 99 }]);
    assert.equal(data.find(d => d.hour === 10).count, 0);
  });

  test('skips runs without timestamp', () => {
    const data = analyzeEngagementByHour([{ success: true, likes: 50 }]);
    assert.equal(data.reduce((s, h) => s + h.count, 0), 0);
  });
});

describe('suggestBestTimes', () => {
  test('returns correct count', () => {
    assert.equal(suggestBestTimes(3).suggestedTimes.length, 3);
  });

  test('each time has hour, label, cron', () => {
    for (const t of suggestBestTimes(2).suggestedTimes) {
      assert.ok(typeof t.hour  === 'number');
      assert.ok(typeof t.label === 'string');
      assert.ok(typeof t.cron  === 'string');
    }
  });

  test('hours in range 0-23', () => {
    for (const t of suggestBestTimes(4).suggestedTimes) {
      assert.ok(t.hour >= 0 && t.hour < 24);
    }
  });

  test('basedOn is industry-defaults when no data', () => {
    assert.equal(suggestBestTimes(1).basedOn, 'industry-defaults');
  });

  test('returns 24-element hourlyData', () => {
    assert.equal(suggestBestTimes(1).hourlyData.length, 24);
  });

  test('message is non-empty string', () => {
    const { message } = suggestBestTimes(1);
    assert.ok(typeof message === 'string' && message.length > 0);
  });
});
