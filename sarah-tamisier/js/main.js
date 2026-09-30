// Menu mobile
const toggle = document.getElementById('navToggle');
const links = document.getElementById('navLinks');
toggle.addEventListener('click', () => {
  const open = links.classList.toggle('is-open');
  toggle.setAttribute('aria-expanded', open);
});
links.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
  links.classList.remove('is-open');
  toggle.setAttribute('aria-expanded', false);
}));

// Bordure de la nav au scroll
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => nav.classList.toggle('is-scrolled', window.scrollY > 10));

// Filtres de projets
document.querySelectorAll('.filter').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.filter').forEach(b => b.classList.remove('is-active'));
  btn.classList.add('is-active');
  const f = btn.dataset.filter;
  document.querySelectorAll('#projectGrid .card').forEach(card => {
    card.classList.toggle('is-hidden', f !== 'all' && card.dataset.cat !== f);
  });
}));

// Apparition au scroll
const revealEls = document.querySelectorAll('.section__head, .card, .about, .skill, .contact');
revealEls.forEach(el => el.classList.add('reveal'));
const io = new IntersectionObserver(entries => entries.forEach(e => {
  if (e.isIntersecting) { e.target.classList.add('is-visible'); io.unobserve(e.target); }
}), { threshold: 0.15 });
revealEls.forEach(el => io.observe(el));

document.getElementById('year').textContent = new Date().getFullYear();
