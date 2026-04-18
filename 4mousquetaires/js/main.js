/* ================================================
   4 MOUSQUETAIRES — Main JS
   ================================================ */

(function () {
  'use strict';

  // --- Nav scroll behavior ---
  const nav = document.querySelector('.nav');
  if (nav) {
    const hero = document.querySelector('.hero');
    if (hero) {
      const observer = new IntersectionObserver(
        ([entry]) => nav.classList.toggle('scrolled', !entry.isIntersecting),
        { threshold: 0 }
      );
      observer.observe(hero);
    } else {
      nav.classList.add('scrolled');
    }
  }

  // --- Mobile nav toggle ---
  const burger = document.querySelector('.nav__burger');
  if (burger && nav) {
    burger.addEventListener('click', () => nav.classList.toggle('nav--open'));
    document.addEventListener('click', (e) => {
      if (nav.classList.contains('nav--open') && !nav.contains(e.target)) {
        nav.classList.remove('nav--open');
      }
    });
  }

  // --- Active nav link ---
  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav__link, .nav__mobile-link').forEach((link) => {
    const href = link.getAttribute('href') || '';
    if (href === currentPath || (currentPath === '' && href === 'index.html')) {
      link.classList.add('active');
    }
  });

  // --- Scroll reveal ---
  const revealEls = document.querySelectorAll('.reveal');
  if (revealEls.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    revealEls.forEach((el) => observer.observe(el));
  }

  // --- FAQ accordion ---
  document.querySelectorAll('.faq-question').forEach((btn) => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq-item');
      const isOpen = item.classList.contains('open');
      document.querySelectorAll('.faq-item.open').forEach((el) => el.classList.remove('open'));
      if (!isOpen) item.classList.add('open');
    });
  });

  // --- Portfolio / project modals ---
  const modalBackdrop = document.getElementById('project-modal');
  if (modalBackdrop) {
    const modalTitle    = modalBackdrop.querySelector('.modal__title');
    const modalClient   = modalBackdrop.querySelector('.modal__client');
    const modalDesc     = modalBackdrop.querySelector('.modal__desc');
    const modalTags     = modalBackdrop.querySelector('.modal__tags');
    const modalVideoEl  = modalBackdrop.querySelector('.modal__video');
    const modalClose    = modalBackdrop.querySelector('.modal__close');

    function openModal(card) {
      if (modalTitle)  modalTitle.textContent  = card.dataset.title  || '';
      if (modalClient) modalClient.textContent = card.dataset.client || '';
      if (modalDesc)   modalDesc.textContent   = card.dataset.desc   || '';
      if (modalTags)   modalTags.innerHTML     = (card.dataset.tags  || '').split(',').map(t => `<span class="badge badge--primary">${t.trim()}</span>`).join('');
      if (modalVideoEl && card.dataset.video) {
        modalVideoEl.innerHTML = `<iframe src="${card.dataset.video}" allowfullscreen></iframe>`;
      } else if (modalVideoEl) {
        modalVideoEl.innerHTML = '<div class="video-placeholder"><div class="video-placeholder__label"><span>▶</span><span>Vidéo à venir</span></div></div>';
      }
      modalBackdrop.classList.add('open');
      document.body.style.overflow = 'hidden';
    }

    function closeModal() {
      modalBackdrop.classList.remove('open');
      document.body.style.overflow = '';
      if (modalVideoEl) modalVideoEl.innerHTML = '';
    }

    document.querySelectorAll('[data-modal="project"]').forEach((card) => {
      card.addEventListener('click', () => openModal(card));
    });

    if (modalClose) modalClose.addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', (e) => { if (e.target === modalBackdrop) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  }

  // --- Contact / Career form submit (demo) ---
  document.querySelectorAll('.js-form').forEach((form) => {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const btn = form.querySelector('[type="submit"]');
      if (btn) {
        btn.textContent = 'Envoi en cours…';
        btn.disabled = true;
      }
      setTimeout(() => {
        showToast('Message envoyé ! On revient vers vous sous 48h.', 'success');
        form.reset();
        if (btn) {
          btn.textContent = btn.dataset.label || 'Envoyer';
          btn.disabled = false;
        }
      }, 1400);
    });
  });

  // --- Toast ---
  function showToast(message, type = 'success') {
    let toast = document.querySelector('.toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'toast';
      document.body.appendChild(toast);
    }
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✓' : '✕'}</span><span>${message}</span>`;
    toast.classList.add('show');
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => toast.classList.remove('show'), 4500);
  }

  // --- Blog filter tabs ---
  const filterBtns = document.querySelectorAll('.blog-filter-btn');
  if (filterBtns.length) {
    filterBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        filterBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const cat = btn.dataset.cat;
        document.querySelectorAll('.blog-item').forEach((item) => {
          item.style.display = (cat === 'all' || item.dataset.cat === cat) ? '' : 'none';
        });
      });
    });
  }

  // --- Smooth scroll for anchor links ---
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
        if (nav) nav.classList.remove('nav--open');
      }
    });
  });

  // --- Video autoplay on hover (project cards) ---
  document.querySelectorAll('.card__thumb video[data-preview]').forEach((video) => {
    const card = video.closest('.card, .portfolio-item');
    if (!card) return;
    card.addEventListener('mouseenter', () => { video.play(); });
    card.addEventListener('mouseleave', () => { video.pause(); video.currentTime = 0; });
  });
})();
