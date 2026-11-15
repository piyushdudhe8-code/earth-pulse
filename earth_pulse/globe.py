"""Interactive 3D Earth hero for EARTH PULSE.

The surface texture is NASA's Blue Marble imagery as distributed with the
three-globe examples. The renderer and globe geometry are powered by Three.js.
The page is embedded in Streamlit as an isolated, responsive HTML component.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


interactive_earth_component = components.declare_component(
    "earth_pulse_interactive_earth_v2",
    path=str(Path(__file__).with_name("earth_globe_component")),
)


EARTH_GLOBE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    * { box-sizing: border-box; }
    html, body {
      width: 100%; height: 100%; margin: 0; overflow: hidden;
      background: transparent;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    #stage {
      position: relative; width: 100%; height: 100%; min-height: 320px;
      overflow: hidden; isolation: isolate;
      background:
        radial-gradient(ellipse at 52% 48%, rgba(12, 74, 65, .30), transparent 48%),
        radial-gradient(ellipse at 55% 54%, rgba(4, 20, 28, .16), transparent 70%);
      border-radius: 24px;
    }
    #stage:fullscreen {
      position: fixed; inset: 0; width: 100vw; height: 100vh; height: 100dvh;
      min-height: 100vh; min-height: 100dvh; border-radius: 0; z-index: 9999;
    }
    #globe {
      position: absolute; inset: 0; width: 100%; height: 100%; display: block;
      cursor: grab; touch-action: none;
    }
    #globe:active { cursor: grabbing; }
    .globe-kicker {
      position: absolute; z-index: 2; top: 18px; left: 18px;
      color: #9be7c4; font-size: 10px; font-weight: 800;
      letter-spacing: .19em; text-transform: uppercase;
      text-shadow: 0 2px 12px rgba(0,0,0,.55);
      pointer-events: none;
    }
    .globe-controls {
      position: absolute; z-index: 4; top: 14px; right: 14px;
      display: flex; gap: 7px; padding: 6px;
      border: 1px solid rgba(132, 207, 179, .25);
      border-radius: 14px; background: rgba(5, 22, 22, .62);
      backdrop-filter: blur(10px);
    }
    .globe-controls button {
      display: grid; place-items: center; width: 38px; height: 38px;
      padding: 0; border: 1px solid rgba(132, 207, 179, .2);
      border-radius: 10px; background: rgba(19, 52, 48, .85);
      color: #d7f4e5; font: 600 21px/1 Inter, ui-sans-serif, system-ui, sans-serif;
      cursor: pointer; transition: background .15s ease, border-color .15s ease;
    }
    .globe-controls button:hover,
    .globe-controls button:focus-visible {
      border-color: #9be7c4; background: rgba(44, 99, 82, .95);
      outline: 2px solid rgba(155, 231, 196, .45); outline-offset: 2px;
    }
    .globe-controls button:active { background: rgba(62, 125, 102, .95); }
    .globe-controls button:focus:not(:focus-visible) { outline: none; }
    .globe-caption {
      position: absolute; z-index: 2; left: 50%; bottom: 14px; transform: translateX(-50%);
      width: max-content; max-width: calc(100% - 28px);
      padding: 8px 13px; border: 1px solid rgba(132, 207, 179, .28);
      border-radius: 999px; background: rgba(5, 22, 22, .60);
      color: #bad7cb; font-size: 10px; letter-spacing: .08em;
      text-align: center; backdrop-filter: blur(10px); pointer-events: none;
    }
    .globe-caption strong { color: #a9efca; font-weight: 700; }
    #status {
      position: absolute; z-index: 3; inset: auto 14px 48px 14px;
      color: #c4d9d0; text-align: center; font-size: 11px;
      pointer-events: none; opacity: 0; transition: opacity .25s ease;
    }
    #status.show { opacity: 1; }
    @media (max-width: 640px) {
      #stage { min-height: 320px; }
      .globe-kicker { top: 12px; left: 12px; }
      .globe-controls { top: 42px; right: 9px; gap: 4px; padding: 4px; }
      .globe-controls button { width: 34px; height: 34px; font-size: 19px; }
      .globe-caption { bottom: 10px; font-size: 9px; }
      #status { bottom: 44px; }
    }
    @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
  </style>
</head>
<body>
  <div id="stage">
    <div class="globe-kicker">EARTH SYSTEMS · PLANET VIEW</div>
    <canvas id="globe" aria-label="Interactive three-dimensional Earth globe. Drag to rotate." role="img"></canvas>
    <div class="globe-controls" role="group" aria-label="Earth globe controls">
      <button id="zoom-in" type="button" aria-label="Zoom in" title="Zoom in">+</button>
      <button id="zoom-out" type="button" aria-label="Zoom out" title="Zoom out">−</button>
      <button id="reset-view" type="button" aria-label="Reset view" title="Reset view">↺</button>
      <button id="fullscreen" type="button" aria-label="Enter fullscreen" title="Enter fullscreen">⛶</button>
    </div>
    <div id="status" class="show">Loading satellite Earth texture…</div>
    <div class="globe-caption"><strong>NASA BLUE MARBLE</strong> &nbsp;·&nbsp; Drag to rotate · Scroll to zoom</div>
  </div>

  <script type="importmap">
    {
      "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"
      }
    }
  </script>
  <script type="module">
    const statusEl = document.getElementById('status');
    const canvas = document.getElementById('globe');
    const stage = document.getElementById('stage');
    const zoomInButton = document.getElementById('zoom-in');
    const zoomOutButton = document.getElementById('zoom-out');
    const resetButton = document.getElementById('reset-view');
    const fullscreenButton = document.getElementById('fullscreen');

    try {
      const THREE = await import('three');
      const { OrbitControls } = await import('https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js');
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
      camera.position.set(0, 0, 5);

      const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'high-performance' });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.18;

      const sceneGroup = new THREE.Group();
      scene.add(sceneGroup);
      const selectedLocation = __EARTH_PULSE_LOCATION__;

      scene.add(new THREE.AmbientLight(0x91bed0, 1.05));
      const sun = new THREE.DirectionalLight(0xfff2dc, 2.45);
      sun.position.set(-3.8, 2.1, 4.6);
      scene.add(sun);
      const blueFill = new THREE.DirectionalLight(0x1c7ca0, 0.52);
      blueFill.position.set(3.5, -1.2, -3.5);
      scene.add(blueFill);

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.target.set(0, 0, 0);
      controls.enableDamping = true;
      controls.dampingFactor = 0.06;
      controls.enablePan = false;
      controls.rotateSpeed = 0.65;
      controls.zoomSpeed = 0.8;
      controls.minPolarAngle = 0.01;
      controls.maxPolarAngle = Math.PI - 0.01;

      const loader = new THREE.TextureLoader();
      loader.setCrossOrigin('anonymous');
      const earthTextureUrl = 'https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg';

      const earthGeometry = new THREE.SphereGeometry(1.42, 112, 112);
      const fallbackMaterial = new THREE.MeshPhongMaterial({ color: 0x164f68, shininess: 18, specular: 0x397f94 });
      const earth = new THREE.Mesh(earthGeometry, fallbackMaterial);
      sceneGroup.add(earth);
      if (selectedLocation) {
        const latitude = THREE.MathUtils.degToRad(selectedLocation.latitude);
        const longitude = THREE.MathUtils.degToRad(selectedLocation.longitude + 180);
        const radius = 1.47;
        const marker = new THREE.Mesh(
          new THREE.SphereGeometry(0.045, 18, 18),
          new THREE.MeshBasicMaterial({ color: 0xffd166 })
        );
        marker.position.set(
          -radius * Math.cos(latitude) * Math.cos(longitude),
          radius * Math.sin(latitude),
          radius * Math.cos(latitude) * Math.sin(longitude)
        );
        sceneGroup.add(marker);
      }

      const cloudsGeometry = new THREE.SphereGeometry(1.435, 96, 96);
      let clouds = null;

      // A restrained Fresnel shell gives the thin blue atmospheric limb.
      const atmosphereMaterial = new THREE.ShaderMaterial({
        vertexShader: `
          varying vec3 vNormal;
          varying vec3 vViewPosition;
          void main() {
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            vNormal = normalize(normalMatrix * normal);
            vViewPosition = -mvPosition.xyz;
            gl_Position = projectionMatrix * mvPosition;
          }
        `,
        fragmentShader: `
          varying vec3 vNormal;
          varying vec3 vViewPosition;
          void main() {
            float rim = 1.0 - max(dot(normalize(vNormal), normalize(vViewPosition)), 0.0);
            float glow = pow(rim, 2.35);
            gl_FragColor = vec4(0.16, 0.62, 0.92, glow * 0.78);
          }
        `,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        transparent: true,
        depthWrite: false
      });
      const atmosphere = new THREE.Mesh(new THREE.SphereGeometry(1.51, 96, 96), atmosphereMaterial);
      sceneGroup.add(atmosphere);

      // Quiet star field, kept dim so the planet remains the focal point.
      const starPositions = [];
      let seed = 417;
      const random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
      for (let i = 0; i < 1250; i++) {
        const radius = 5.8 + random() * 5.5;
        const theta = random() * Math.PI * 2;
        const phi = Math.acos(2 * random() - 1);
        starPositions.push(
          radius * Math.sin(phi) * Math.cos(theta),
          radius * Math.cos(phi),
          radius * Math.sin(phi) * Math.sin(theta)
        );
      }
      const starGeometry = new THREE.BufferGeometry();
      starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3));
      const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0xc5e9e3, size: 0.018, transparent: true, opacity: 0.58, sizeAttenuation: true }));
      scene.add(stars);

      loader.load(earthTextureUrl, (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
        earth.material.dispose();
        earth.material = new THREE.MeshPhongMaterial({
          map: texture,
          color: 0xffffff,
          specular: new THREE.Color(0x315c72),
          shininess: 13
        });
        statusEl.classList.remove('show');

        // The NASA/Blue Marble texture already contains satellite-observed
        // cloud cover. This lightweight outer shell supplies gentle depth.
        const cloudMaterial = new THREE.MeshPhongMaterial({
          color: 0xffffff, transparent: true, opacity: 0.10,
          side: THREE.FrontSide, depthWrite: false
        });
        clouds = new THREE.Mesh(cloudsGeometry, cloudMaterial);
        sceneGroup.add(clouds);
      }, undefined, () => {
        statusEl.textContent = 'Earth texture unavailable — check internet access.';
        statusEl.classList.add('show');
      });

      sceneGroup.rotation.x = 0.12;
      sceneGroup.rotation.y = -0.48;
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      controls.autoRotate = !reducedMotion;
      controls.autoRotateSpeed = 0.35;

      let fitDistance = 0;
      const resize = () => {
        const width = Math.max(1, canvas.clientWidth);
        const height = Math.max(1, canvas.clientHeight);
        const previousZoom = fitDistance
          ? camera.position.distanceTo(controls.target) / fitDistance
          : 1.25;
        const direction = camera.position.clone().sub(controls.target).normalize();

        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        const verticalFov = THREE.MathUtils.degToRad(camera.fov);
        const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
        const limitingFov = Math.min(verticalFov, horizontalFov);
        const nextFitDistance = 1.58 / Math.sin(limitingFov / 2) * 1.12;

        controls.minDistance = nextFitDistance;
        controls.maxDistance = nextFitDistance * 2.2;
        camera.position.copy(controls.target).addScaledVector(
          direction,
          THREE.MathUtils.clamp(
            nextFitDistance * previousZoom,
            controls.minDistance,
            controls.maxDistance
          )
        );
        camera.updateProjectionMatrix();
        fitDistance = nextFitDistance;
        controls.update();
      };
      const observer = new ResizeObserver(resize);
      observer.observe(stage);
      resize();
      controls.saveState();

      zoomInButton.addEventListener('click', () => {
        const direction = camera.position.clone().sub(controls.target).normalize();
        const distance = camera.position.distanceTo(controls.target) / 1.2;
        camera.position.copy(controls.target).addScaledVector(
          direction,
          THREE.MathUtils.clamp(distance, controls.minDistance, controls.maxDistance)
        );
        controls.update();
      });
      zoomOutButton.addEventListener('click', () => {
        const direction = camera.position.clone().sub(controls.target).normalize();
        const distance = camera.position.distanceTo(controls.target) * 1.2;
        camera.position.copy(controls.target).addScaledVector(
          direction,
          THREE.MathUtils.clamp(distance, controls.minDistance, controls.maxDistance)
        );
        controls.update();
      });
      resetButton.addEventListener('click', () => {
        controls.reset();
        controls.update();
      });

      const updateFullscreenButton = () => {
        const isFullscreen = document.fullscreenElement === stage;
        const label = isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen';
        fullscreenButton.textContent = isFullscreen ? '×' : '⛶';
        fullscreenButton.setAttribute('aria-label', label);
        fullscreenButton.title = label;
        requestAnimationFrame(resize);
      };
      fullscreenButton.addEventListener('click', async () => {
        try {
          if (document.fullscreenElement === stage) {
            await document.exitFullscreen();
          } else if (stage.requestFullscreen) {
            await stage.requestFullscreen();
          } else {
            throw new Error('Fullscreen is not supported by this browser.');
          }
        } catch (error) {
          statusEl.textContent = error.message || 'Fullscreen could not be opened.';
          statusEl.classList.add('show');
        }
      });
      document.addEventListener('fullscreenchange', updateFullscreenButton);
      window.addEventListener('resize', resize);

      let frame = 0;
      const animate = () => {
        frame = requestAnimationFrame(animate);
        controls.update();
        if (clouds) clouds.rotation.y += 0.00016;
        stars.rotation.y -= 0.000025;
        renderer.render(scene, camera);
      };
      animate();

      window.addEventListener('beforeunload', () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        window.removeEventListener('resize', resize);
        document.removeEventListener('fullscreenchange', updateFullscreenButton);
        controls.dispose();
        renderer.dispose();
      }, { once: true });
    } catch (error) {
      statusEl.textContent = '3D globe could not start. Check browser WebGL and internet access.';
      statusEl.classList.add('show');
      console.error('EARTH PULSE globe error:', error);
    }
  </script>
</body>
</html>"""


def render_earth_globe(
    height: int = 500,
    latitude: float | None = None,
    longitude: float | None = None,
) -> None:
    """Render an interactive, responsive 3D Earth in the Streamlit page."""
    location = (
        {"latitude": latitude, "longitude": longitude}
        if latitude is not None and longitude is not None
        else None
    )
    html = EARTH_GLOBE_HTML.replace(
        "__EARTH_PULSE_LOCATION__", json.dumps(location, allow_nan=False)
    )
    components.html(html, height=height, scrolling=False)


def render_interactive_earth_globe(
    height: int = 560,
    selected_location: dict[str, float] | None = None,
    key: str = "earth_pulse_interactive_earth",
) -> dict | None:
    """Render the raycast-enabled globe and return clicked coordinates."""
    return interactive_earth_component(
        height=height,
        selected=selected_location,
        key=key,
        default=None,
    )
