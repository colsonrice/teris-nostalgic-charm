/* Teri's Nostalgic Charm — small motion enhancements
   Progressive only: the page is fully usable without JS. */

(() => {
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  // ---------- Scroll reveal for grid items only ----------
  // Section headings stay always-visible — readability over choreography.
  const targets = document.querySelectorAll(
    ".card, .theme, .spread__layout, .rail-card"
  );
  targets.forEach((el) => el.classList.add("reveal"));

  if ("IntersectionObserver" in window && !prefersReducedMotion) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e, i) => {
          if (e.isIntersecting) {
            // Slight stagger for grids
            const delay = Math.min(i * 35, 320);
            e.target.style.transitionDelay = `${delay}ms`;
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.05, rootMargin: "0px 0px -4% 0px" }
    );
    targets.forEach((t) => io.observe(t));

    // Safety net — anything still hidden after 1.6s (e.g. tab inactive,
    // observer race) gets revealed unconditionally.
    setTimeout(() => {
      targets.forEach((t) => t.classList.add("is-in"));
    }, 1600);
  } else {
    targets.forEach((t) => t.classList.add("is-in"));
  }

  // ---------- Subtle pointer parallax on hero plate ----------
  const plate = document.querySelector(".hero__plate");
  if (plate && !prefersReducedMotion) {
    const wrap = plate.parentElement;
    let raf = 0;
    const set = (x, y) => {
      plate.style.transform =
        `rotate(${-1.6 + x * 0.8}deg) translate3d(${x * 6}px, ${y * 6}px, 0)`;
    };
    wrap.addEventListener("pointermove", (e) => {
      const r = wrap.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => set(x, y));
    });
    wrap.addEventListener("pointerleave", () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => set(0, 0));
    });
  }

  // ---------- Tiny rail nudge ----------
  const rail = document.querySelector(".rail");
  if (rail) {
    let down = false, startX = 0, scrollLeft = 0;
    rail.addEventListener("pointerdown", (e) => {
      down = true;
      startX = e.pageX - rail.offsetLeft;
      scrollLeft = rail.scrollLeft;
    });
    const stop = () => (down = false);
    rail.addEventListener("pointerup", stop);
    rail.addEventListener("pointerleave", stop);
    rail.addEventListener("pointermove", (e) => {
      if (!down) return;
      const x = e.pageX - rail.offsetLeft;
      rail.scrollLeft = scrollLeft - (x - startX);
    });
  }

  // ---------- Reflect current section in nav ----------
  const sections = ["catalog", "themes", "letter", "shop"]
    .map((id) => document.getElementById(id))
    .filter(Boolean);
  const links = document.querySelectorAll(".nav a[href^='#']");
  if (sections.length && "IntersectionObserver" in window) {
    const io2 = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.id;
            links.forEach((l) => {
              const active = l.getAttribute("href") === `#${id}`;
              l.style.color = active ? "var(--ink)" : "";
              l.style.fontWeight = active ? "600" : "";
            });
          }
        });
      },
      { rootMargin: "-30% 0px -55% 0px" }
    );
    sections.forEach((s) => io2.observe(s));
  }
})();
