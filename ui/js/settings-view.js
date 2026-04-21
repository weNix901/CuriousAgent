// ui/js/settings-view.js
/* Settings view logic for v0.3.3 */

let currentConfig = {};

async function loadSettings() {
  try {
    const response = await fetch('/api/config');
    currentConfig = await response.json();
    
    // Populate DeepRead config
    if (currentConfig.deepread) {
      document.getElementById('overlap-percent').value = 
        currentConfig.deepread.extraction?.paragraph_overlap_percent || 15;
      document.getElementById('overlap-percent-value').textContent = 
        currentConfig.deepread.extraction?.paragraph_overlap_percent || 15;
      document.getElementById('context-extend').value = 
        currentConfig.deepread.extraction?.context_extend_paragraphs || 2;
      document.getElementById('completeness-min').value = 
        currentConfig.deepread.quality?.completeness_min || 2;
    }
    
    // Populate temperature config
    if (currentConfig.temperature_system) {
      document.getElementById('temperature-enabled').checked = 
        currentConfig.temperature_system.enabled ?? true;
      document.getElementById('decay-factor').value = 
        currentConfig.temperature_system.decay_factor || 0.95;
      document.getElementById('decay-factor-value').textContent = 
        currentConfig.temperature_system.decay_factor || 0.95;
      document.getElementById('hot-threshold').value = 
        currentConfig.temperature_system.hot_threshold || 80;
      document.getElementById('warm-threshold').value = 
        currentConfig.temperature_system.warm_threshold || 30;
    }
    
    // Populate archive config
    if (currentConfig.archive_strategy) {
      document.getElementById('archive-enabled').checked = 
        currentConfig.archive_strategy.enabled ?? false;
      document.getElementById('archive-temperature').value = 
        currentConfig.archive_strategy.trigger_temperature || 30;
      document.getElementById('delete-txt').checked = 
        currentConfig.archive_strategy.delete_txt ?? true;
      document.getElementById('compress-pdf').checked = 
        currentConfig.archive_strategy.compress_pdf ?? true;
    }
  } catch (error) {
    console.error('Failed to load settings:', error);
  }
}

async function updateDeepReadConfig(key, value) {
  if (!currentConfig.deepread) currentConfig.deepread = {};
  if (!currentConfig.deepread.extraction) currentConfig.deepread.extraction = {};
  
  currentConfig.deepread.extraction[key] = parseInt(value);
  await saveConfig();
}

async function updateTemperatureConfig(key, value) {
  if (!currentConfig.temperature_system) currentConfig.temperature_system = {};
  currentConfig.temperature_system[key] = parseFloat(value);
  await saveConfig();
}

async function toggleTemperature(enabled) {
  if (!currentConfig.temperature_system) currentConfig.temperature_system = {};
  currentConfig.temperature_system.enabled = enabled;
  await saveConfig();
}

async function toggleArchive(enabled) {
  if (!currentConfig.archive_strategy) currentConfig.archive_strategy = {};
  currentConfig.archive_strategy.enabled = enabled;
  await saveConfig();
}

async function updateArchiveConfig(key, value) {
  if (!currentConfig.archive_strategy) currentConfig.archive_strategy = {};
  if (typeof value === 'boolean') {
    currentConfig.archive_strategy[key] = value;
  } else {
    currentConfig.archive_strategy[key] = parseInt(value);
  }
  await saveConfig();
}

async function saveConfig() {
  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentConfig)
    });
  } catch (error) {
    console.error('Failed to save config:', error);
  }
}

async function resetConfig() {
  if (confirm('确定要重置为默认配置吗？')) {
    await fetch('/api/config/reset', { method: 'POST' });
    await loadSettings();
  }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', loadSettings);