/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "on-tertiary-fixed": "#141d21",
        "on-tertiary-fixed-variant": "#3f484d",
        "inverse-surface": "#27313e",
        "tertiary-fixed": "#dbe4ea",
        "on-secondary": "#ffffff",
        "surface-container-lowest": "#ffffff",
        "surface-tint": "#00658b",
        "surface-container-highest": "#d9e3f4",
        "on-surface": "#121c28",
        "surface-container": "#e5eeff",
        "on-error": "#ffffff",
        "background": "#f8f9ff",
        "surface-container-low": "#eef4ff",
        "on-secondary-container": "#09657f",
        "inverse-primary": "#7cd0ff",
        "on-error-container": "#93000a",
        "surface-dim": "#d1dbec",
        "error": "#ba1a1a",
        "surface-variant": "#d9e3f4",
        "tertiary": "#535b60",
        "secondary-fixed": "#baeaff",
        "surface": "#f8f9ff",
        "inverse-on-surface": "#eaf1ff",
        "secondary": "#0c6780",
        "primary-fixed": "#c4e7ff",
        "on-tertiary": "#ffffff",
        "secondary-fixed-dim": "#89d0ed",
        "primary-container": "#007ba7",
        "on-primary": "#ffffff",
        "on-secondary-fixed-variant": "#004d62",
        "outline": "#6f787f",
        "primary": "#006184",
        "error-container": "#ffdad6",
        "primary-fixed-dim": "#7cd0ff",
        "on-tertiary-container": "#f4faff",
        "on-primary-fixed": "#001e2c",
        "on-surface-variant": "#3f484e",
        "tertiary-fixed-dim": "#bfc8ce",
        "on-secondary-fixed": "#001f29",
        "on-background": "#121c28",
        "outline-variant": "#bfc8cf",
        "secondary-container": "#9ae1ff",
        "on-primary-container": "#f5faff",
        "surface-container-high": "#dfe9fa",
        "tertiary-container": "#6b7479",
        "on-primary-fixed-variant": "#004c69",
        "surface-bright": "#f8f9ff"
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      },
      spacing: {
        "stack-sm": "8px",
        "stack-lg": "32px",
        "unit": "8px",
        "stack-md": "16px",
        "container-padding-desktop": "40px",
        "container-padding-mobile": "20px",
        "section-gap": "64px",
        "gutter": "16px"
      },
      fontFamily: {
        "headline-md": ["Inter", "sans-serif"],
        "headline-lg-mobile": ["Inter", "sans-serif"],
        "body-md": ["Inter", "sans-serif"],
        "label-sm": ["Inter", "sans-serif"],
        "label-md": ["Inter", "sans-serif"],
        "headline-lg": ["Inter", "sans-serif"],
        "display-lg": ["Inter", "sans-serif"],
        "body-lg": ["Inter", "sans-serif"]
      },
      fontSize: {
        "headline-md": [
          "24px",
          {
            "lineHeight": "32px",
            "fontWeight": "600"
          }
        ],
        "headline-lg-mobile": [
          "28px",
          {
            "lineHeight": "36px",
            "fontWeight": "600"
          }
        ],
        "body-md": [
          "16px",
          {
            "lineHeight": "24px",
            "fontWeight": "400"
          }
        ],
        "label-sm": [
          "12px",
          {
            "lineHeight": "16px",
            "fontWeight": "600"
          }
        ],
        "label-md": [
          "14px",
          {
            "lineHeight": "20px",
            "letterSpacing": "0.01em",
            "fontWeight": "500"
          }
        ],
        "headline-lg": [
          "32px",
          {
            "lineHeight": "40px",
            "letterSpacing": "-0.01em",
            "fontWeight": "600"
          }
        ],
        "display-lg": [
          "48px",
          {
            "lineHeight": "56px",
            "letterSpacing": "-0.02em",
            "fontWeight": "700"
          }
        ],
        "body-lg": [
          "18px",
          {
            "lineHeight": "28px",
            "fontWeight": "400"
          }
        ]
      }
    },
  },
  plugins: [],
}
