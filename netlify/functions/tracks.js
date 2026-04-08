const DATABASE_ID = '2fd3666f9ff3475cbd14051cee4c9318';
const NOTION_VERSION = '2022-06-28';

exports.handler = async function(event, context) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers, body: '' };
  }

  const secret = process.env.NOTION_SECRET;
  if (!secret) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'NOTION_SECRET not set' }) };
  }

  try {
    const allResults = [];
    let cursor = undefined;

    do {
      const body = {
        page_size: 100,
        sorts: [{ timestamp: 'created_time', direction: 'descending' }],
      };
      if (cursor) body.start_cursor = cursor;

      const res = await fetch(
        `https://api.notion.com/v1/databases/${DATABASE_ID}/query`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${secret}`,
            'Notion-Version': NOTION_VERSION,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        }
      );

      if (!res.ok) {
        const err = await res.text();
        return { statusCode: res.status, headers, body: JSON.stringify({ error: err }) };
      }

      const data = await res.json();
      allResults.push(...data.results);
      cursor = data.has_more ? data.next_cursor : undefined;

    } while (cursor);

    // Extract text from any Notion property type
    const getText = (prop) => {
      if (!prop) return null;
      switch (prop.type) {
        case 'title':        return prop.title?.map(t => t.plain_text).join('').trim() || null;
        case 'rich_text':    return prop.rich_text?.map(t => t.plain_text).join('').trim() || null;
        case 'url':          return prop.url || null;
        case 'select':       return prop.select?.name || null;
        case 'multi_select': return prop.multi_select?.map(s => s.name) || [];
        case 'files':
          // Notion file/media properties
          if (prop.files && prop.files.length > 0) {
            const f = prop.files[0];
            return f.type === 'external' ? f.external?.url : f.file?.url || null;
          }
          return null;
        default: return null;
      }
    };

    const tracks = allResults.map((page) => {
      const p = page.properties;

      // Log property names from the first page to help debug
      const propNames = Object.keys(p);

      const workingTitle = getText(p['aka (working title)']) || getText(p['Name']) || 'Untitled';
      const finalName    = getText(p['Final Name (if exists)']) || null;

      // Feel/genre
      let feel = getText(p['How does it sound?']) || [];
      if (typeof feel === 'string') {
        feel = feel.split(/[,\/]/).map(s => s.trim()).filter(Boolean);
      }

      // Audio — try multiple possible property names
      const audio = getText(p['AUDIO']) || getText(p['Audio']) || getText(p['audio']) || null;

      // Gear
      let gear = getText(p['Gear Used']) || getText(p['gear']) || [];
      if (typeof gear === 'string') {
        gear = gear.split(',').map(s => s.trim()).filter(Boolean);
      }

      const hasVocals = (Array.isArray(feel) ? feel : [feel]).some(f =>
        f && (f.toLowerCase().includes('vocal') || f.toLowerCase().includes('has vocal'))
      );
      const feelClean = (Array.isArray(feel) ? feel : [feel]).filter(f =>
        f && !f.toLowerCase().includes('has vocal')
      );

      return {
        id: page.id,
        title: workingTitle,
        finalName,
        feel: feelClean,
        audio,
        gear: Array.isArray(gear) ? gear : [],
        hasVocals,
        // Include property names in first result only for debugging
        _propNames: propNames,
      };
    });

    // Strip debug info after first track
    const firstTrack = tracks[0];
    tracks.slice(1).forEach(t => delete t._propNames);

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ tracks }),
    };

  } catch (err) {
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: err.message }),
    };
  }
};
