/* ============================================================
   I-96 Home Buyers — interactions
   ============================================================ */
(function () {
  'use strict';

  /* ---- Year ---- */
  var y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

  /* ---- Theme toggle ---- */
  (function () {
    var t = document.querySelector('[data-theme-toggle]');
    var r = document.documentElement;
    var d = matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light';
    r.setAttribute('data-theme', d);
    if (!t) return;
    t.addEventListener('click', function () {
      d = d === 'dark' ? 'light' : 'dark';
      r.setAttribute('data-theme', d);
      t.setAttribute('aria-label', 'Switch to ' + (d === 'dark' ? 'light' : 'dark') + ' mode');
      t.innerHTML =
        d === 'dark'
          ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
          : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    });
  })();

  /* ---- Sticky header shadow ---- */
  var header = document.getElementById('header');
  var onScroll = function () {
    if (window.scrollY > 12) header.classList.add('header--scrolled');
    else header.classList.remove('header--scrolled');
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---- Mobile nav ---- */
  var navToggle = document.getElementById('navToggle');
  var nav = document.getElementById('nav');
  if (navToggle && nav) {
    navToggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        nav.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  /* ---- Scroll reveal ---- */
  var reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );
    reveals.forEach(function (el) {
      io.observe(el);
    });
    // Safety fallback: ensure nothing stays invisible if observer misfires.
    setTimeout(function () {
      reveals.forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (r.top < window.innerHeight) el.classList.add('in');
      });
    }, 1200);
  } else {
    reveals.forEach(function (el) {
      el.classList.add('in');
    });
  }

  /* ---- Lead form ---- */
  var API = '';
  var form = document.getElementById('leadForm');
  var success = document.getElementById('formSuccess');
  var submitBtn = document.getElementById('submitBtn');

  function setError(name, msg) {
    var field = form.querySelector('[name="' + name + '"]');
    var holder = field ? field.closest('.field') : null;
    var msgEl = form.querySelector('[data-msg-for="' + name + '"]');
    if (holder) holder.classList.toggle('field--error', !!msg);
    if (msgEl) msgEl.textContent = msg || '';
  }

  function validEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  }
  function validPhone(v) {
    return (v.replace(/\D/g, '').length >= 10);
  }

  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var data = {
        address: form.address.value.trim(),
        name: form.name.value.trim(),
        phone: form.phone.value.trim(),
        email: form.email.value.trim(),
        condition: form.condition.value,
        timeline: form.timeline.value,
      };

      var ok = true;
      ['address', 'name', 'phone', 'email'].forEach(function (k) {
        setError(k, '');
      });
      if (!data.address) { setError('address', 'Please enter the property address.'); ok = false; }
      if (!data.name) { setError('name', 'Please enter your name.'); ok = false; }
      if (!validPhone(data.phone)) { setError('phone', 'Enter a valid phone number.'); ok = false; }
      if (!validEmail(data.email)) { setError('email', 'Enter a valid email address.'); ok = false; }
      if (!ok) {
        var firstErr = form.querySelector('.field--error input, .field--error select');
        if (firstErr) firstErr.focus();
        return;
      }

      submitBtn.disabled = true;
      var original = submitBtn.textContent;
      submitBtn.textContent = 'Sending…';

      fetch(API + '/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
        .then(function (res) {
          if (!res.ok) throw new Error('Request failed');
          return res.json();
        })
        .then(function () {
          form.style.display = 'none';
          success.classList.add('active');
          success.scrollIntoView({ behavior: 'smooth', block: 'center' });
        })
        .catch(function () {
          submitBtn.disabled = false;
          submitBtn.textContent = original;
          var msgEl = form.querySelector('[data-msg-for="email"]');
          if (msgEl) msgEl.textContent = 'Something went wrong. Please call us or try again.';
        });
    });

    /* Clear error on input */
    form.querySelectorAll('input, select').forEach(function (el) {
      el.addEventListener('input', function () {
        setError(el.name, '');
      });
    });
  }
})();

/* ===== Hero VSL video: click-to-load YouTube embed ===== */
(function () {
  var frame = document.getElementById('vslFrame');
  var playBtn = document.getElementById('vslPlay');
  if (!frame || !playBtn) return;

  function loadVideo() {
    var id = (frame.getAttribute('data-youtube') || '').trim();
    if (!id) {
      // No video ID set yet — gently let the user know.
      var cap = frame.querySelector('.hero__video-caption');
      if (cap) cap.textContent = 'Video coming soon';
      return;
    }
    var iframe = document.createElement('iframe');
    iframe.src = 'https://www.youtube-nocookie.com/embed/' + id +
      '?autoplay=1&mute=1&rel=0&modestbranding=1&playsinline=1';
    iframe.title = 'I-96 Home Buyers video';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    iframe.allowFullscreen = true;
    frame.innerHTML = '';
    frame.appendChild(iframe);
  }

  playBtn.addEventListener('click', loadVideo);
  var placeholder = frame.querySelector('.hero__video-placeholder');
  if (placeholder) placeholder.addEventListener('click', function (e) {
    if (e.target !== playBtn) loadVideo();
  });
})();
