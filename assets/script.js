(() => {
  const root = document.documentElement;
  const button = document.getElementById('theme-toggle');
  const themes = ['system', 'light', 'dark'];
  const saved = localStorage.getItem('portfolio-theme');

  if (saved && themes.includes(saved)) root.dataset.theme = saved;

  const updateLabel = () => {
    if (!button) return;
    const current = root.dataset.theme || 'system';
    button.textContent = `Theme: ${current}`;
    button.setAttribute('aria-label', `Current theme is ${current}. Activate to change theme.`);
  };

  if (button) {
    button.addEventListener('click', () => {
      const current = root.dataset.theme || 'system';
      const next = themes[(themes.indexOf(current) + 1) % themes.length];
      root.dataset.theme = next;
      localStorage.setItem('portfolio-theme', next);
      updateLabel();
    });
  }

  const year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();
  updateLabel();

  const articles = [
    {
      slug: 'mcp-dotnet-build-mcp-server-csharp',
      title: 'MCP in .NET: What It Actually Solves and How to Build an MCP Server in C#',
      description: 'MCP architecture, ASP.NET Core tools, SDK 2.0 stateless HTTP, MRTR, security, Clean Architecture, and when a normal API is still better.',
      published: '2026-08-31'
    },
    {
      slug: 'dotnet-11-9-new-features-that-actually-matter',
      title: '.NET 11: 9 New Features That Actually Matter to Developers',
      description: 'C# 15 unions, runtime async, request compression, FullJoin, encrypted ZIPs, Blazor, vector search, MAUI, and NativeAOT—the .NET 11 changes worth watching.',
      published: '2026-08-21'
    },
    {
      slug: 'aspnet-core-rate-limiting-noisy-client',
      title: 'One Noisy Client Can Slow Everyone Down—Fix Your ASP.NET Core Rate Limiting',
      description: 'A production-minded ASP.NET Core 10 guide to rate-limit partitions, authenticated client identity, reverse proxies, endpoint cost, 429 responses, queueing, and multi-instance deployment trade-offs.',
      published: '2026-08-14'
    },
    {
      slug: 'ef-core-pagination-page-numbers-vs-cursors',
      title: 'Your EF Core Pagination Is Slower Than You Think—Skip/Take Is Only Part of the Story',
      description: 'Offset pagination, exact page counts, keyset pagination, stable ordering, indexes, and the database work hidden behind a simple UI choice.',
      published: '2026-08-11'
    },
    {
      slug: 'ef-core-entities-not-api-contracts',
      title: 'Stop Exposing EF Core Entities from Your .NET 10 APIs',
      description: 'Explicit API contracts, EF Core projections, TypedResults, ProblemDetails, and fewer accidental coupling points.',
      published: '2026-08-10'
    },
    {
      slug: 'clean-architecture-dotnet-10-without-ceremony',
      title: 'Clean Architecture in .NET 10: Stop Adding Layers, Start Protecting Decisions',
      description: 'One order feature end to end: UUIDv7, domain invariants, authoritative pricing, EF Core boundaries, Minimal APIs, and focused tests.',
      published: '2026-08-07'
    },
    {
      slug: 'clean-architecture-vs-ddd',
      title: 'Clean Architecture vs. DDD Is Usually the Wrong Question',
      description: 'One organizes dependencies; the other models business complexity. Strong systems often use both, selectively.',
      published: '2026-08-06'
    }
  ];

  const articleMatch = window.location.pathname.match(/^\/articles\/([^/]+)\/?$/);
  if (!articleMatch) return;

  const slug = articleMatch[1];
  const current = articles.find(article => article.slug === slug);
  if (!current) return;

  const canonicalUrl = `https://darawsheh.github.io/articles/${slug}/`;
  const imageUrl = `https://darawsheh.github.io/assets/og/${slug}.svg`;
  const authorProfileUrl = 'https://darawsheh.github.io/islam-darawsheh/';
  const authorPersonId = `${authorProfileUrl}#person`;

  const ensureMeta = (selector, attributes) => {
    let node = document.head.querySelector(selector);
    if (!node) {
      node = document.createElement('meta');
      document.head.appendChild(node);
    }
    Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, value));
  };

  if (!document.head.querySelector('link[rel="icon"]')) {
    const icon = document.createElement('link');
    icon.rel = 'icon';
    icon.type = 'image/svg+xml';
    icon.href = '/favicon.svg';
    document.head.appendChild(icon);
  }

  if (!document.head.querySelector('link[rel="alternate"][type="application/rss+xml"]')) {
    const feed = document.createElement('link');
    feed.rel = 'alternate';
    feed.type = 'application/rss+xml';
    feed.title = 'Islam Darawsheh Articles';
    feed.href = '/feed.xml';
    document.head.appendChild(feed);
  }

  ensureMeta('meta[property="og:site_name"]', {
    property: 'og:site_name',
    content: 'Islam Darawsheh'
  });
  ensureMeta('meta[property="og:image"]', {
    property: 'og:image',
    content: imageUrl
  });
  ensureMeta('meta[property="og:image:alt"]', {
    property: 'og:image:alt',
    content: current.title
  });
  ensureMeta('meta[name="twitter:card"]', {
    name: 'twitter:card',
    content: 'summary_large_image'
  });
  ensureMeta('meta[name="twitter:image"]', {
    name: 'twitter:image',
    content: imageUrl
  });
  ensureMeta('meta[name="twitter:image:alt"]', {
    name: 'twitter:image:alt',
    content: current.title
  });

  for (const node of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const data = JSON.parse(node.textContent);
      if (['TechArticle', 'Article', 'BlogPosting'].includes(data['@type'])) {
        data['@type'] = 'BlogPosting';
        data.image = [imageUrl];
        data.author = {
          '@id': authorPersonId,
          '@type': 'Person',
          name: 'Islam Darawsheh',
          url: authorProfileUrl,
          sameAs: [
            'https://github.com/Darawsheh',
            'https://www.linkedin.com/in/darawsheh/'
          ]
        };
        data.isPartOf = {
          '@type': 'Blog',
          '@id': 'https://darawsheh.github.io/articles/',
          name: 'Islam Darawsheh Articles'
        };
        node.textContent = JSON.stringify(data, null, 2);
        break;
      }
    } catch {
      // Leave unrelated or malformed JSON-LD untouched.
    }
  }

  if (!document.querySelector('script[data-seo-breadcrumbs]')) {
    const breadcrumbData = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'Home',
          item: 'https://darawsheh.github.io/'
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'Articles',
          item: 'https://darawsheh.github.io/articles/'
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: current.title,
          item: canonicalUrl
        }
      ]
    };
    const breadcrumbJson = document.createElement('script');
    breadcrumbJson.type = 'application/ld+json';
    breadcrumbJson.dataset.seoBreadcrumbs = 'true';
    breadcrumbJson.textContent = JSON.stringify(breadcrumbData, null, 2);
    document.head.appendChild(breadcrumbJson);
  }

  const article = document.querySelector('article.article');
  if (article && !article.querySelector('.breadcrumbs')) {
    const nav = document.createElement('nav');
    nav.className = 'breadcrumbs';
    nav.setAttribute('aria-label', 'Breadcrumb');

    const home = document.createElement('a');
    home.href = '/';
    home.textContent = 'Home';
    nav.appendChild(home);

    const separator1 = document.createElement('span');
    separator1.setAttribute('aria-hidden', 'true');
    separator1.textContent = '›';
    nav.appendChild(separator1);

    const articleList = document.createElement('a');
    articleList.href = '/articles/';
    articleList.textContent = 'Articles';
    nav.appendChild(articleList);

    const separator2 = document.createElement('span');
    separator2.setAttribute('aria-hidden', 'true');
    separator2.textContent = '›';
    nav.appendChild(separator2);

    const here = document.createElement('span');
    here.setAttribute('aria-current', 'page');
    here.textContent = current.title;
    nav.appendChild(here);

    article.prepend(nav);
  }

  if (article && !article.querySelector('.related-articles')) {
    const related = articles.filter(item => item.slug !== slug).slice(0, 3);
    if (related.length) {
      const section = document.createElement('section');
      section.className = 'related-articles';
      section.setAttribute('aria-labelledby', 'related-articles-title');

      const eyebrow = document.createElement('p');
      eyebrow.className = 'eyebrow';
      eyebrow.textContent = 'Continue reading';
      section.appendChild(eyebrow);

      const heading = document.createElement('h2');
      heading.id = 'related-articles-title';
      heading.textContent = 'Related articles';
      section.appendChild(heading);

      const list = document.createElement('ul');
      for (const item of related) {
        const li = document.createElement('li');
        const link = document.createElement('a');
        link.href = `/articles/${item.slug}/`;
        link.textContent = item.title;
        const summary = document.createElement('span');
        summary.textContent = item.description;
        li.append(link, summary);
        list.appendChild(li);
      }
      section.appendChild(list);

      const comments = article.querySelector('.comments');
      const footer = article.querySelector('.article-footer');
      article.insertBefore(section, comments || footer || null);
    }
  }

  const footerActions = article?.querySelector('.article-footer .actions');
  if (footerActions && !footerActions.querySelector('a[href="/islam-darawsheh/"]')) {
    const profileLink = document.createElement('a');
    profileLink.className = 'button';
    profileLink.href = '/islam-darawsheh/';
    profileLink.textContent = 'Author profile';
    footerActions.prepend(profileLink);
  }
})();
