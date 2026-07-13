# GDPR Agent Browser Connector

This Manifest V3 extension sends browser-history evidence directly to the local GDPR Agent bridge. It requires no cloud relay. History permission is optional and requested by the user from the extension options page. Page bodies, form fields, passwords, payment data, cookies and page screenshots are not captured.

## Install locally

1. Run `npm test` and `npm run build` in this directory.
2. In Chromium, open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select `browser-extension/dist`.
3. Create a browser connector and one-time pairing token in GDPR Agent Settings.
4. Open the extension options, enter the local bridge URL, connector instance ID and token, then explicitly enable browser history.
5. Use **Backfill history** once; incremental visits then queue locally and retry until acknowledged.

The queue is bounded at 5,000 records and refuses to silently discard overflow. Pairing tokens are kept only in extension-local storage and stored only as hashes by GDPR Agent. Revoking a pairing stops future sync without deleting already-grounded evidence.
