const { performance } = require('perf_hooks');

// Mock data generator
function generateHistory(count) {
    const types = ['text', 'web_url', 'media', 'file', 'screenshot'];
    const items = [];
    for (let i = 0; i < count; i++) {
        items.push({
            id: `item-${i}`,
            timestamp: Date.now(),
            value: `This is a sample history item number ${i} with some random text content`,
            type: types[i % types.length],
        });
    }
    return items;
}

// Current implementation logic (simulated)
function filterCurrent(history, searchQuery) {
    return history.filter(item =>
        item.value.toLowerCase().includes(searchQuery.toLowerCase())
    );
}

// Optimized logic (simulated safety check)
function filterOptimized(history, searchQuery) {
    const lowerQuery = searchQuery.toLowerCase();
    return history.filter(item => {
        const val = item.value;
        return val && val.toLowerCase().includes(lowerQuery);
    });
}

const COUNT = 10000;
const QUERY = "500"; // Should match some items

console.log(`Generating ${COUNT} items...`);
const history = generateHistory(COUNT);

console.log('Running benchmark...');

// Measure Current
const startCurrent = performance.now();
for (let i = 0; i < 1000; i++) {
    filterCurrent(history, QUERY);
}
const endCurrent = performance.now();
const timeCurrent = (endCurrent - startCurrent) / 1000;

console.log(`Current Implementation (Average of 1000 runs): ${timeCurrent.toFixed(4)} ms per filter`);

// Measure Optimized (Safe)
const startOptimized = performance.now();
for (let i = 0; i < 1000; i++) {
    filterOptimized(history, QUERY);
}
const endOptimized = performance.now();
const timeOptimized = (endOptimized - startOptimized) / 1000;

console.log(`Optimized (Safe) Implementation (Average of 1000 runs): ${timeOptimized.toFixed(4)} ms per filter`);

console.log('\nAnalysis:');
console.log(`By using useMemo, we save ~${timeCurrent.toFixed(4)} ms of blocking JS thread time on every render where 'history' and 'searchQuery' have not changed.`);
