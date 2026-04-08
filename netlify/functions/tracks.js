const DATABASE_ID = '1aa9e578d45980da9b93e7f346f89c07';
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
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: 'NOTION_SECRET environment variable not set' }),
    };
  }

  try {
    const allResults = [];
    let cursor = undefined;

    // Notion paginates at 100 — loop until we have everything
    do {
      const body = {
        page_size: 100,
        sorts: [{ timestamp: 'created_time', direction: 'ascending' }],
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

    // Helper to extract values from Notion property types
    const getText = (prop) => {
      if (!prop) return null;
      switch (prop.type) {
        case 'title':     return prop.title?.map(t => t.plain_text).join('').trim() || null;
        case 'rich_text': return prop.rich_text?.map(t => t.plain_text).join('').trim() || null;
        case 'url':       return prop.url || null;
        case 'select':    return prop.select?.name || null;
        case 'multi_select': return prop.multi_select?.map(s => s.name) || [];
        default:          return null;
      }
    };

    const tracks = allResults.map((page) => {
      const p = page.properties;

      const workingTitle = getText(p['aka (working title)']) || 'Untitled';
      const finalName    = getText(p['Final Name (if exists)']) || null;

      // Feel/genre — try multi_select first, fall back to rich_text
      let feel = getText(p['How does it sound?']) || [];
      if (typeof feel === 'string') {
        feel = feel.split(/[,\/]/).map(s => s.trim()).filter(Boolean);
      }

      const audio = getText(p['AUDIO']) || null;

      // Gear — try rich_text, split on commas
      let gear = getText(p['Gear Used']) || [];
      if (typeof gear === 'string') {
        gear = gear.split(',').map(s => s.trim()).filter(Boolean);
      }

      const hasVocals = feel.some(f =>
        f.toLowerCase().includes('vocal') || f.toLowerCase().includes('has vocal')
      );

      // Remove "has vocals" from feel tags since we handle it separately
      const feelClean = feel.filter(f => !f.toLowerCase().includes('has vocal'));

      return {
        id: page.id,
        title: workingTitle,
        finalName,
        feel: feelClean,
        audio,
        gear: Array.isArray(gear) ? gear : [],
        hasVocals,
      };
    });

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
