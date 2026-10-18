// Prooflytics Client Scripts: Chart initialization and accessible Provenance Modals

function initCharts() {
  if (typeof Chart === 'undefined') return;

  document.querySelectorAll('canvas[data-chart]').forEach(canvas => {
    if (canvas.chartInstance) {
      canvas.chartInstance.destroy();
    }
    try {
      const rawData = canvas.getAttribute('data-chart');
      if (!rawData) return;
      const parsed = JSON.parse(rawData);

      const isLine = canvas.getAttribute('data-chart-type') === 'line';

      canvas.chartInstance = new Chart(canvas, {
        type: isLine ? 'line' : 'bar',
        data: {
          labels: parsed.labels || [],
          datasets: (parsed.datasets || []).map(ds => ({
            label: ds.label || '',
            data: ds.data || [],
            backgroundColor: isLine ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.8)',
            borderColor: '#3b82f6',
            borderWidth: 2,
            tension: 0.2,
            fill: isLine
          }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: '#94a3b8' }
            }
          },
          scales: {
            x: {
              ticks: { color: '#94a3b8' },
              grid: { color: '#334155' }
            },
            y: {
              ticks: { color: '#94a3b8' },
              grid: { color: '#334155' }
            }
          }
        }
      });
    } catch (err) {
      console.error('Chart.js render error:', err);
    }
  });
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) closeBtn.focus();
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
  }
}

// Global modal dismiss listeners
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => {
      m.classList.remove('active');
      m.setAttribute('aria-hidden', 'true');
    });
  }
});

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
});

// Re-init on HTMX DOM updates if HTMX is used
document.addEventListener('htmx:afterSwap', () => {
  initCharts();
});
