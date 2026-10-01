/* Post-render image enhancement (loaded after app.js).
   app.js renders initials badges; this layer adds ESPN <img> tags on top:
   team logos on .tlogo spans, player headshots on .avatar spans.
   A failed load removes the <img> (onerror) leaving the initials badge —
   never a broken image. Re-runs on DOM changes (tab switches, filters). */
(function () {
  'use strict';
  var LOGO_SLUG = { LA: 'lar', WAS: 'wsh' };
  var logoSlug = function (abbr) {
    return (LOGO_SLUG[abbr] || String(abbr).toLowerCase());
  };
  var PLAYER_IDS = {}; // "PLAYER|TEAM" -> espn_id
  var IDS_LOADED = false;

  function imgTag(src, cls) {
    return '<img src="' + src + '"' + (cls ? ' class="' + cls + '"' : '') +
      ' alt="" loading="lazy" onerror="this.remove()">';
  }

  function enhanceLogos(root) {
    var spans = (root || document).querySelectorAll('.tlogo:not([data-imgen])');
    for (var i = 0; i < spans.length; i++) {
      var s = spans[i];
      s.setAttribute('data-imgen', '1');
      var abbrEl = s.querySelector('i');
      var abbr = abbrEl ? abbrEl.textContent.trim() : '';
      if (!abbr || s.querySelector('img')) continue;
      var tmp = document.createElement('span');
      tmp.innerHTML = imgTag(
        'https://a.espncdn.com/i/teamlogos/nfl/500/' + logoSlug(abbr) + '.png');
      s.appendChild(tmp.firstChild);
    }
  }

  function playerTeamFor(avatar) {
    // Walk up to the enclosing card, then find the name + team line.
    var card = avatar.parentElement;
    for (var d = 0; d < 4 && card; d++) {
      var nameEl = card.querySelector(':scope > .pid > .pn, :scope > .ppick-id > .ppick-name, :scope > .eid > .pn');
      var metaEl = card.querySelector(':scope > .pid > .pm, :scope > .ppick-id > .ppick-match, :scope > .eid > .pm');
      if (nameEl) {
        var team = '';
        if (metaEl) {
          var m = metaEl.textContent.trim().split('·')[0].trim().split(' ')[0];
          team = (m || '').toUpperCase();
        }
        return { name: nameEl.textContent.trim(), team: team };
      }
      card = card.parentElement;
    }
    return null;
  }

  function enhanceAvatars(root) {
    var avs = (root || document).querySelectorAll('.avatar:not([data-imgen])');
    for (var i = 0; i < avs.length; i++) {
      (function (a) {
        if (a.querySelector('img.hs')) { a.setAttribute('data-imgen','1'); return; }
        if (!IDS_LOADED) return; /* IDs not ready yet — leave unstamped so the post-fetch pass picks this up */
        a.setAttribute('data-imgen', '1');
        var pt = playerTeamFor(a);
        if (!pt) return;
        var id = PLAYER_IDS[pt.name + '|' + pt.team] ||
                 PLAYER_IDS[pt.name + '|'];
        if (!id) return;
        var tmp = document.createElement('span');
        tmp.innerHTML = imgTag(
          'https://a.espncdn.com/i/headshots/nfl/players/full/' +
          encodeURIComponent(id) + '.png', 'hs');
        a.appendChild(tmp.firstChild);
      })(avs[i]);
    }
  }

  function enhance(root) {
    try { enhanceLogos(root); } catch (e) {}
    try { enhanceAvatars(root); } catch (e) {}
  }

  function loadIds() {
    fetch('data/v1/props.json', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var rows = Array.isArray(d) ? d : (d.props || d.rows || []);
        rows.forEach(function (r) {
          if (r.espn_id && r.player) {
            PLAYER_IDS[r.player + '|' + (r.team || '')] = r.espn_id;
            if (!PLAYER_IDS[r.player + '|']) PLAYER_IDS[r.player + '|'] = r.espn_id;
          }
        });
        IDS_LOADED = true;
        enhance();
      })
      .catch(function () {});
  }

  // Re-enhance after app.js re-renders (tabs, filters, search).
  var obs = new MutationObserver(function (muts) {
    for (var i = 0; i < muts.length; i++) {
      if (muts[i].addedNodes.length) { enhance(); break; }
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      enhance(); loadIds();
      obs.observe(document.body, { childList: true, subtree: true });
    });
  } else {
    enhance(); loadIds();
    obs.observe(document.body, { childList: true, subtree: true });
  }
})();
