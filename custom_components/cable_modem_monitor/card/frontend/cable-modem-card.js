/**
 * Cable Modem card: renders the layout the integration builds for a modem.
 *
 * One dependency-free ES module, no build step. The element is defined
 * before anything awaits, because HA waits only two seconds for an
 * undefined `custom:` element. See DASHBOARD_CARD_SPEC.md.
 */

const CARD_TAG = "cable-modem-card";
const COMMAND = "cable_modem_monitor/card_config";
const UNAVAILABLE = "card_unavailable";
// After a failed load, retry no sooner than this: hass updates arrive many times a second.
const RETRY_MS = 30000;

// Options the generator accepts that the editor cannot show. A config that
// carries one keeps the YAML editor, so a form edit never drops it.
const YAML_ONLY_KEYS = ["channel_label", "channel_grouping", "status_card_exclude"];

const LABELS = {
  device_id: "Modem",
  include_status_card: "Status card",
  include_downstream_power: "Downstream power",
  include_downstream_snr: "Downstream SNR",
  include_downstream_frequency: "Downstream frequency",
  include_upstream_power: "Upstream power",
  include_upstream_frequency: "Upstream frequency",
  include_errors: "Error totals",
  include_error_rates: "Error rates",
  include_latency: "Latency",
  graph_hours: "Graph hours",
  short_titles: "Short titles",
};

class CableModemCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    return {
      // One field per line: tests read name and default from these lines.
      schema: [
        { name: "device_id", selector: { device: { integration: "cable_modem_monitor" } } },
        { name: "include_status_card", default: true, selector: { boolean: {} } },
        { name: "include_downstream_power", default: true, selector: { boolean: {} } },
        { name: "include_downstream_snr", default: true, selector: { boolean: {} } },
        { name: "include_downstream_frequency", default: true, selector: { boolean: {} } },
        { name: "include_upstream_power", default: true, selector: { boolean: {} } },
        { name: "include_upstream_frequency", default: true, selector: { boolean: {} } },
        { name: "include_errors", default: true, selector: { boolean: {} } },
        { name: "include_error_rates", default: false, selector: { boolean: {} } },
        { name: "include_latency", default: true, selector: { boolean: {} } },
        { name: "graph_hours", default: 24, selector: { number: { min: 1, max: 168, mode: "box" } } },
        { name: "short_titles", default: true, selector: { boolean: {} } },
      ],
      computeLabel: (field) => LABELS[field.name],
      assertConfig: (config) => {
        const present = YAML_ONLY_KEYS.filter((key) => key in config);
        if (present.length) {
          throw new Error(`Edit in YAML: the form cannot show ${present.join(", ")}`);
        }
      },
    };
  }

  constructor() {
    super();
    this._root = this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._child = null;
    this._watch = [];
    this._watchKey = "";
    this._loading = false;
    this._reload = false;
    this._retryAt = 0;
  }

  setConfig(config) {
    if (config === null || typeof config !== "object") {
      throw new Error("Card configuration must be an object");
    }
    const hours = config.graph_hours;
    if (hours !== undefined && !(Number.isInteger(hours) && hours >= 1 && hours <= 168)) {
      throw new Error("graph_hours must be a whole number from 1 to 168");
    }
    this._config = config;
    this._child = null;
    this._watch = [];
    this._watchKey = "";
    this._retryAt = 0;
    this._load();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._child) {
      this._child.hass = hass;
    }
    if (this._watch.length && this._stateKey() !== this._watchKey) {
      this._load();
    } else if (!this._child && !this._loading && Date.now() >= this._retryAt) {
      this._load();
    }
  }

  getCardSize() {
    return 8;
  }

  _stateKey() {
    return this._watch.map((id) => this._hass.states[id]?.state).join("/");
  }

  _options() {
    const { type, ...options } = this._config;
    return options;
  }

  async _load() {
    if (!this._config || !this._hass) {
      return;
    }
    if (this._loading) {
      this._reload = true;
      return;
    }
    this._loading = true;
    try {
      const result = await this._hass.callWS({ type: COMMAND, options: this._options() });
      const helpers = await window.loadCardHelpers();
      const child = helpers.createCardElement(result.card);
      child.hass = this._hass;
      this._child = child;
      this._watch = result.watch;
      this._watchKey = this._stateKey();
      this._root.replaceChildren(child);
    } catch (err) {
      this._child = null;
      this._watch = [];
      this._retryAt = Date.now() + RETRY_MS;
      this._showMessage(err && err.code === UNAVAILABLE ? err.message : "Could not load the Cable Modem card");
    } finally {
      this._loading = false;
      if (this._reload) {
        this._reload = false;
        this._load();
      }
    }
  }

  _showMessage(text) {
    const card = document.createElement("ha-card");
    const body = document.createElement("div");
    body.style.padding = "16px";
    body.textContent = text;
    card.appendChild(body);
    this._root.replaceChildren(card);
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, CableModemCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Cable Modem",
    description: "Status, signal levels, errors and latency for your cable modem.",
    documentationURL: "https://github.com/solentlabs/cable_modem_monitor",
  });
}
