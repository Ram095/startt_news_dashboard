# Project Changelog

This document tracks all significant changes made to the News Feed Management System.

---

### 10. Re-instated Login Feature

*   **Why:** The user login feature was previously disabled for development purposes. This change re-enables the authentication flow.
*   **How:** The temporary bypass in the main application logic was removed, requiring all users to authenticate before accessing the dashboard.
*   **Where:** `app/main.py`
*   **What:**
    *   Removed the conditional check `if not config.get('features.enable_user_management', False):` that was bypassing the login page.
    *   The application now defaults to showing the login page if the user is not authenticated.

---

### 9. Stateful Tab Navigation

*   **Why:** After editing an article and saving the changes, the user was redirected to the default "Dashboard" tab instead of remaining on the "Articles" tab, creating a disruptive user experience.
*   **How:** The stateless `st.tabs` component was replaced with a stateful `st.radio` component, styled with custom CSS to mimic the appearance of tabs. The active tab is now stored in `st.session_state`, allowing the application to control the view after a `st.rerun()`.
*   **Where:** `app/main.py`
*   **What:**
    *   Added CSS to the main stylesheet to make `st.radio` buttons look like tabs.
    *   Replaced the `st.tabs` call and its `with tabs[x]:` blocks with a single `st.radio` widget and a series of `if/elif` blocks to render the active tab's content.
    *   The save handler for article edits now sets `st.session_state.active_tab = "📰 Articles"` before the rerun, ensuring the user remains on the correct page.

---

### 8. Article AI Summary Editing

*   **Why:** The user needed the ability to manually correct or refine the AI-generated summary for an article directly from the user interface.
*   **How:** An "Edit" button was added to each article card. When clicked, it reveals a text area pre-filled with the AI summary and a "Save" button to persist the changes. This was accomplished by adding a new method to the data repository and updating the UI rendering logic.
*   **Where:**
    *   `app/repository/repository.py`
    *   `app/main.py`
*   **What:**
    *   A new `update_article_ai_summary` method was added to the `ArticleRepository` to handle the SQL `UPDATE` operation.
    *   The `render_article_card` function was modified to include an "📝 Edit" button.
    *   Session state (`st.session_state`) is now used to toggle the visibility of a `st.text_area` for editing.
    *   The main application loop was updated to include a handler that calls the new repository method when an article's summary is saved.

---

### 7. Database Connection and Pathing Issues

*   **Why:** The application was failing with an "unable to open database file" error because it was trying to access the database using a relative path that was incorrect depending on the script's execution directory.
*   **How:** The system was refactored to build an absolute path to the database file, ensuring it could always be found. This was achieved by making the `Settings` class aware of the project's root directory and using this information to construct the full path.
*   **Where:**
    *   `app/config/settings.py`
    *   `app/main.py`
*   **What:**
    *   The `Settings` class was updated to calculate and store the project's root directory.
    *   The `init_system` function was modified to use this project root to create an absolute path to the database file defined in `config.yaml`.
    *   A temporary diagnostic function, `test_database_connection`, was added to log the resolved database path and article count on startup to verify the connection.

---

### 6. Scraper Data Pipeline and State Management

*   **Why:** The "Pull Data" button appeared to run successfully but no new articles were being saved. This was caused by the scraper scripts writing their state files (`_seen_urls.json`) to the wrong directory and ignoring the configured output path for their CSV files.
*   **How:** The system was re-engineered to make the scrapers stateless by passing the output path as a command-line argument. The `ScraperManager` was updated to provide this path and the state files were co-located with the output data.
*   **Where:**
    *   All scraper scripts in the `scripts/` directory.
    *   `app/services/manager.py`
    *   `app/main.py`
*   **What:**
    *   The `argparse` library was added to all scraper scripts to accept an `--output` argument.
    *   The `ScraperManager` was updated to pass the configured `csv_output` path to the scripts via this argument.
    *   All scrapers were modified to save their `_seen_urls.json` file in the same directory as their output CSV.
    *   The `clear_scraper_caches` function was fixed to look for these state files in their new, correct location within the `data/` directory.

---

### 5. Firebase Authentication `INVALID_EMAIL` Error

*   **Why:** The login process was failing with a `400 Bad Request` and an `INVALID_EMAIL` error from the Firebase API.
*   **How:** The authentication requests were modified to explicitly include the Firebase API key. This is a necessary workaround for a known issue in some versions of the `pyrebase` library where the key is not automatically included, leading to a malformed request.
*   **Where:** `app/auth/firebase_config.py`
*   **What:**
    *   The `auth.sign_in_with_email_and_password` and `auth.create_user_with_email_and_password` calls were replaced with direct `requests.post` calls to the appropriate Google Identity Toolkit API endpoints.
    *   The API key was added to the request URL, and the user credentials were sent in the JSON payload.

---

### 4. SVG Logo Integration

*   **Why:** The user requested the integration of a company logo into the dashboard's header.
*   **How:** A helper function was created to read the SVG file from the `assets` directory, encode it into Base64, and render it as an image within a `st.markdown` component.
*   **Where:** `app/main.py`
*   **What:**
    *   A `render_svg` function was added to handle file reading, encoding, and rendering.
    *   This function was called within the top bar of the `show_dashboard` function to place the logo in the top-left corner.

---

### 3. Asynchronous Execution Errors

*   **Why:** The application was throwing a `RuntimeError` because the login page was attempting to create a new asyncio event loop while one was already being managed by Streamlit.
*   **How:** The conflicting code was refactored to use a single, unified event loop. All asynchronous functions were marked with `async def` and called with `await`.
*   **Where:**
    *   `app/main.py`
    *   `app/auth/login_page.py`
*   **What:**
    *   The `main` and `show_login_page` functions were converted to `async` functions.
    *   Manual event loop management (`asyncio.new_event_loop()`, `loop.run_until_complete()`) was removed and replaced with `await`.
    *   The application's entry point was updated to `asyncio.run(main())`.

---

### 2. Scraper Script Configuration

*   **Why:** The dashboard displayed a "No scrapers configured" message because the application was unable to locate the scraper scripts.
*   **How:** The paths in the `config.yaml` file were corrected to be relative to the project's root directory, which is the working directory when Streamlit is launched.
*   **Where:** `config.yaml`
*   **What:**
    *   The `script_path` for each scraper was changed from an incorrect relative path (e.g., `../scripts/script.py`) to the correct one (e.g., `scripts/script.py`).

---

### 1. Streamlit `st.dialog` Compatibility

*   **Why:** The application failed to start, throwing an `AttributeError` because `st.dialog` was not available in the installed version of Streamlit.
*   **How:** The native `@st.dialog` decorator was replaced with a custom modal implementation using `st.session_state` to control the visibility of the dialogs.
*   **Where:** `app/main.py`
*   **What:**
    *   A "dialog router" was added to the `show_dashboard` function to conditionally render a dialog based on a value in `st.session_state`.
    *   Buttons that previously opened a dialog were modified to set this session state value and trigger a `st.rerun()`.
    *   The dialog functions themselves were updated to be standard functions that render UI elements directly. 