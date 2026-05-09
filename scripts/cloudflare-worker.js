/**
 * Cloudflare Worker for Infortic Images
 * Serves images from R2 bucket with caching and optimization
 * 
 * Deploy to: https://infortic-images.gerrymoeis.workers.dev
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const key = url.pathname.slice(1); // Remove leading slash

    // Handle root path
    if (!key || key === '') {
      return new Response('Infortic Images CDN - Powered by Cloudflare R2', {
        status: 200,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }

    // Only allow WebP images
    if (!key.endsWith('.webp')) {
      return new Response('Only WebP images are supported', {
        status: 400,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }

    try {
      // Get object from R2
      const object = await env.INFORTIC_IMAGES.get(key);

      if (object === null) {
        return new Response('Image not found', {
          status: 404,
          headers: {
            'Content-Type': 'text/plain',
          },
        });
      }

      // Return image with proper headers
      const headers = new Headers();
      object.writeHttpMetadata(headers);
      headers.set('Content-Type', 'image/webp');
      headers.set('Cache-Control', 'public, max-age=31536000, immutable'); // 1 year
      headers.set('Access-Control-Allow-Origin', '*'); // Allow CORS
      headers.set('X-Content-Type-Options', 'nosniff');

      return new Response(object.body, {
        headers,
      });
    } catch (error) {
      return new Response(`Error: ${error.message}`, {
        status: 500,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }
  },
};
