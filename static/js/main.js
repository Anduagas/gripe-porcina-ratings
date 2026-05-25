function colorRating(valor) {
  const v = parseFloat(valor);
  if (isNaN(v)) return 'var(--text-muted)';

  if (v < 3)       return `hsl(0, 80%, ${45 + (v - 1) * 5}%)`;
  else if (v < 5)  return `hsl(${20 + (v - 3) * 10}, 85%, 55%)`;
  else if (v < 8)  return `hsl(${45 + (v - 5) * 5}, 90%, 55%)`;
  else             return `hsl(${100 + (v - 8) * 10}, 70%, 50%)`;
}

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('[data-rating]').forEach(el => {
    el.style.color = colorRating(el.dataset.rating);
  });
});

// ── Versiones en tema detalle ──────────────────────────

function cambiarVersion(el) {
  document.querySelectorAll('.version-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');

  const url = el.dataset.url;
  const spoiler = el.querySelector('.vbadge.spoiler');

  if (spoiler) {
    const wrapper = document.querySelector('.video-wrapper');
    wrapper.innerHTML = `
      <div class="spoiler-warning">
        <i class="ti ti-eye-off" style="font-size:32px; margin-bottom:8px;"></i>
        <p>Esta versión contiene <strong>spoilers</strong></p>
        <button class="btn btn-secondary" onclick="cargarVideo('${url}')" style="margin-top:12px; width:auto;">
          Mostrar de todas formas
        </button>
      </div>`;
  } else {
    cargarVideo(url);
  }
}

function cargarVideo(url) {
  const wrapper = document.querySelector('.video-wrapper');
  wrapper.innerHTML = `
    <video controls autoplay preload="metadata" style="width:100%; border-radius:10px; background:#000;">
      <source src="${url}" type="video/webm">
    </video>`;
}

// ── Agregar tema: seleccionar versión ─────────────────

function seleccionarVersion(grupoIndex, versionIndex) {
  const grupo = window._grupos[grupoIndex];
  const v = grupo.versiones[versionIndex];

  document.getElementById('f-anime_nombre').value = v.anime_nombre;
  document.getElementById('f-anime_slug').value = v.anime_slug;
  document.getElementById('f-tipo').value = v.tipo;
  document.getElementById('f-numero').value = v.numero;
  document.getElementById('f-video_url').value = v.video_url;
  document.getElementById('f-nc').value = v.nc || false;
  document.getElementById('f-resolution').value = v.resolution || '';
  document.getElementById('f-source').value = v.source || '';
  document.getElementById('f-spoiler').value = v.spoiler || false;
  document.getElementById('f-version').value = v.version || 1;
  document.getElementById('f-episodes').value = v.episodes || '';
  document.getElementById('f-titulo_cancion').value = v.titulo_cancion || '';
  document.getElementById('f-imagen_url').value = v.imagen_url || '';
  document.getElementById('f-basename').value = v.basename || '';

  const esOP = v.tipo === 'OP';
  const tipoBadge = document.getElementById('v-tipo-badge');
  tipoBadge.textContent = `${v.tipo}${v.numero}`;
  tipoBadge.className = `actividad-tipo ${esOP ? 'op' : 'ed'}`;
  document.getElementById('v-anime-nombre').textContent = v.anime_nombre;
  document.getElementById('v-basename').textContent = v.basename;
  document.getElementById('v-badges').innerHTML = generarBadgesHTML(v);

  const videoEl = document.getElementById('video-preview');
  document.getElementById('video-preview-src').src = v.video_url;
  videoEl.load();

  document.getElementById('panel-video').style.display = 'block';
  document.getElementById('agregar-layout').className = 'agregar-layout-split';
  document.getElementById('panel-video').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function generarBadgesHTML(v) {
  let html = '';
  if (v.resolution) html += `<span class="vbadge res">${v.resolution}p</span>`;
  if (v.nc) html += `<span class="vbadge nc">NC</span>`;
  if (v.source) html += `<span class="vbadge src">${v.source}</span>`;
  if (v.subbed) html += `<span class="vbadge sub">SUB</span>`;
  if (v.lyrics) html += `<span class="vbadge lyr">LYR</span>`;
  if (v.spoiler) html += `<span class="vbadge spoiler">SPOILER</span>`;
  return html;
}

function cancelarSeleccion() {
  document.getElementById('panel-video').style.display = 'none';
  document.getElementById('agregar-layout').className = 'agregar-layout-single';
}