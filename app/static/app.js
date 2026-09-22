(() => {
    "use strict";

    // ============================================================
    // AutoPulse Executive Frontend
    // VIN-first vehicle intelligence experience
    // Source-aware reliability pass:
    // unavailable evidence is never rendered as zero
    // ============================================================

    const API = {
        health: "/health",

        decisionByVin: (vin) =>
            `/api/v1/decision/vin/${encodeURIComponent(vin)}`,

        safetyRatings: "/api/v1/safety-ratings",

        trends: "/api/v1/trends",

        analyst: "/api/v1/analyst",
    };


    // ============================================================
    // STATE
    // ============================================================

    const state = {
        currentVin: null,
        currentVehicle: null,
        currentDecision: null,
        currentNcap: null,
        currentTrend: null,
        reportReady: false,
        analystBusy: false,
        analystRequestId: 0,
        requestId: 0,
        toastTimer: null
    };


    const el = {};


    // ============================================================
    // DOM CACHE
    // ============================================================

    function byId(id) {
        return document.getElementById(id);
    }


    function cacheElements() {
        const ids = [
            "sidebar",
            "sidebarCloseButton",
            "sidebarOverlay",
            "sidebarToggleButton",

            "vinInput",
            "vinSearchButton",
            "searchError",

            "emptyState",
            "loadingState",
            "loadingMessage",
            "resultsContainer",

            "vehicleTitle",
            "vehicleSubtitle",
            "vehicleTypeBadge",
            "fuelTypeBadge",
            "confidenceBadge",
            "sourceAvailabilityBadge",

            "riskGauge",
            "riskScore",
            "attentionLevel",

            "ownershipDecision",
            "ownershipRecommendation",
            "decisionDrivers",

            "identityMake",
            "identityModel",
            "identityYear",
            "identityBody",
            "identityDrive",
            "identityOrigin",

            "nhtsaVinLink",
            "nhtsaRecallLink",
            "nhtsaRatingsLink",
            "carfaxReportLink",

            "complaintCount",
            "recallCount",
            "crashCount",
            "fireCount",
            "injuryCount",
            "deathCount",

            "realWorldIssueList",

            "ncapCoverage",
            "ncapOverall",
            "ncapFront",
            "ncapSide",
            "ncapRollover",

            "trendSignalBadge",
            "trendChart",
            "trendYear",
            "trendLatestCount",
            "trendBaseline",
            "trendAcceleration",
            "trendYtdLabel",
            "trendYtdCount",
            "trendYtdThrough",
            "trendMethodologyNote",
            "recentIssueList",

            "recallBadge",
            "recallUrgency",
            "recallScopeLabel",
            "recallScopeNote",
            "recallList",

            "analystVehicleLabel",
            "analystEvidenceStatus",
            "analystStatus",
            "analystQuestion",
            "analystAskButton",
            "analystResponse",

            "toast",
            "toastTitle",
            "toastMessage"
        ];

        ids.forEach((id) => {
            el[id] = byId(id);
        });
    }


    // ============================================================
    // BASIC DOM HELPERS
    // ============================================================

    function show(node) {
        if (node) {
            node.classList.remove("hidden");
        }
    }


    function hide(node) {
        if (node) {
            node.classList.add("hidden");
        }
    }


    function setText(node, value, fallback = "—") {
        if (!node) {
            return;
        }

        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            node.textContent = fallback;
            return;
        }

        node.textContent = String(value);
    }


    function clearNode(node) {
        if (!node) {
            return;
        }

        while (node.firstChild) {
            node.removeChild(node.firstChild);
        }
    }


    function createElement(
        tag,
        className = "",
        text = null
    ) {
        const node =
            document.createElement(tag);

        if (className) {
            node.className =
                className;
        }

        if (
            text !== null &&
            text !== undefined
        ) {
            node.textContent =
                String(text);
        }

        return node;
    }


    // ============================================================
    // FORMATTERS
    // ============================================================

    function clamp(
        value,
        min,
        max
    ) {
        const number =
            Number(value);

        if (!Number.isFinite(number)) {
            return min;
        }

        return Math.min(
            Math.max(
                number,
                min
            ),
            max
        );
    }


    function normalizeVin(value) {
        return String(
            value || ""
        )
            .toUpperCase()
            .replace(
                /\s+/g,
                ""
            )
            .trim();
    }


    function validateVin(vin) {
        if (!vin) {
            return (
                "Enter a VIN to begin."
            );
        }

        if (vin.length !== 17) {
            return (
                "VIN must contain exactly 17 characters."
            );
        }

        if (
            !/^[A-HJ-NPR-Z0-9]{17}$/.test(
                vin
            )
        ) {
            return (
                "VIN contains invalid characters. " +
                "VINs do not use I, O or Q."
            );
        }

        return null;
    }


    // ------------------------------------------------------------
    // IMPORTANT:
    // JavaScript Number(null) is 0.
    //
    // AutoPulse must never convert missing / unavailable
    // safety evidence into a real zero.
    // ------------------------------------------------------------

    function hasMetricValue(value) {
        return !(
            value === null ||
            value === undefined ||
            value === ""
        );
    }


    function formatNumber(value) {
        if (!hasMetricValue(value)) {
            return "—";
        }

        const number =
            Number(value);

        if (!Number.isFinite(number)) {
            return "—";
        }

        return new Intl.NumberFormat(
            "en-US"
        ).format(number);
    }


    function formatDecimal(
        value,
        digits = 1
    ) {
        if (!hasMetricValue(value)) {
            return "—";
        }

        const number =
            Number(value);

        if (!Number.isFinite(number)) {
            return "—";
        }

        return number.toFixed(
            digits
        );
    }


    function formatPercent(
        value,
        digits = 1
    ) {
        if (!hasMetricValue(value)) {
            return "—";
        }

        const number =
            Number(value);

        if (!Number.isFinite(number)) {
            return "—";
        }

        const sign =
            number > 0
                ? "+"
                : "";

        return (
            `${sign}${number.toFixed(
                digits
            )}%`
        );
    }


    function formatLabel(value) {
        if (!value) {
            return "—";
        }

        return String(value)
            .replace(
                /_/g,
                " "
            )
            .replace(
                /\s+/g,
                " "
            )
            .trim()
            .toLowerCase()
            .replace(
                /\b\w/g,
                (letter) =>
                    letter.toUpperCase()
            );
    }


    function vehicleDisplayName(
        vehicle = {}
    ) {
        return [
            vehicle.model_year,
            vehicle.make,
            vehicle.model
        ]
            .filter(Boolean)
            .join(" ") ||
            "Vehicle";
    }


    function buildQuery(params) {
        const query =
            new URLSearchParams();

        Object.entries(
            params
        ).forEach(
            ([key, value]) => {
                if (
                    value !== null &&
                    value !== undefined &&
                    value !== ""
                ) {
                    query.set(
                        key,
                        String(value)
                    );
                }
            }
        );

        return query.toString();
    }


    // ============================================================
    // SOURCE AVAILABILITY HELPERS
    // ============================================================

    function getSourceState(
        payload,
        sourceName
    ) {
        const sourceMap =
            payload
                ?.source_availability
                ?.sources ||
            payload
                ?.source_availability ||
            {};

        const source =
            sourceMap?.[
                sourceName
            ] || {};

        return {
            available:
                source.available === true,

            recordCount:
                hasMetricValue(
                    source.record_count
                )
                    ? Number(
                        source.record_count
                    )
                    : null,

            message:
                source.message || null
        };
    }


    function metricText(
        value,
        available = true
    ) {
        if (!available) {
            return "Unavailable";
        }

        return formatNumber(
            value
        );
    }


    // ============================================================
    // FETCH
    // ============================================================

    function parseApiError(
        payload,
        status
    ) {
        if (
            typeof payload
                ?.detail ===
            "string"
        ) {
            return payload.detail;
        }

        if (
            typeof payload
                ?.message ===
            "string"
        ) {
            return payload.message;
        }

        if (
            Array.isArray(
                payload?.detail
            )
        ) {
            const messages =
                payload.detail
                    .map(
                        (item) =>
                            item?.msg
                    )
                    .filter(Boolean);

            if (messages.length) {
                return messages.join(
                    " "
                );
            }
        }

        return (
            `Request failed with status ${status}.`
        );
    }


    async function fetchJson(
        url,
        {
            timeout = 60000,
            method = "GET",
            headers = {},
            body = null
        } = {}
    ) {
        const controller =
            new AbortController();

        const timeoutHandle =
            window.setTimeout(
                () =>
                    controller.abort(),
                timeout
            );

        try {
            const response =
                await fetch(
                    url,
                    {
                        method,

                        headers: {
                            Accept:
                                "application/json",

                            ...headers
                        },

                        body,

                        signal:
                            controller.signal
                    }
                );


            const contentType =
                response.headers.get(
                    "content-type"
                ) || "";


            let payload = null;


            if (
                contentType.includes(
                    "application/json"
                )
            ) {
                payload =
                    await response.json();

            } else {
                const text =
                    await response.text();

                payload =
                    text
                        ? {
                            detail: text
                        }
                        : null;
            }


            if (!response.ok) {
                throw new Error(
                    parseApiError(
                        payload,
                        response.status
                    )
                );
            }


            return payload;

        } catch (error) {

            if (
                error?.name ===
                "AbortError"
            ) {
                throw new Error(
                    "The request timed out. " +
                    "NHTSA may be responding slowly. " +
                    "Please retry."
                );
            }

            throw error;

        } finally {

            window.clearTimeout(
                timeoutHandle
            );
        }
    }


    // ============================================================
    // FEEDBACK
    // ============================================================

    function clearError() {
        if (!el.searchError) {
            return;
        }

        el.searchError.textContent =
            "";

        hide(
            el.searchError
        );
    }


    function showError(message) {
        if (!el.searchError) {
            return;
        }

        el.searchError.textContent =
            message;

        show(
            el.searchError
        );
    }


    function setButtonBusy(
        busy,
        text = "Analyzing..."
    ) {
        if (!el.vinSearchButton) {
            return;
        }

        if (
            !el
                .vinSearchButton
                .dataset
                .defaultText
        ) {
            el
                .vinSearchButton
                .dataset
                .defaultText =
                    el
                        .vinSearchButton
                        .textContent
                        .trim();
        }


        el.vinSearchButton.disabled =
            busy;


        el
            .vinSearchButton
            .classList
            .toggle(
                "is-loading",
                busy
            );


        el.vinSearchButton.textContent =
            busy
                ? text
                : el
                    .vinSearchButton
                    .dataset
                    .defaultText;
    }


    function showToast(
        title,
        message,
        type = "info"
    ) {
        if (
            !el.toast ||
            !el.toastTitle ||
            !el.toastMessage
        ) {
            return;
        }


        if (state.toastTimer) {
            clearTimeout(
                state.toastTimer
            );
        }


        el.toast.className =
            `toast toast-${type}`;


        el.toastTitle.textContent =
            title;

        el.toastMessage.textContent =
            message;


        show(
            el.toast
        );


        state.toastTimer =
            window.setTimeout(
                () => {
                    hide(
                        el.toast
                    );
                },
                4000
            );
    }


    function showLoading(message) {
        hide(
            el.emptyState
        );

        hide(
            el.resultsContainer
        );

        show(
            el.loadingState
        );

        setText(
            el.loadingMessage,
            message
        );
    }


    function updateLoading(message) {
        setText(
            el.loadingMessage,
            message
        );
    }


    function showResults() {
        hide(
            el.emptyState
        );

        hide(
            el.loadingState
        );

        show(
            el.resultsContainer
        );
    }


    function showInitialState() {
        hide(
            el.loadingState
        );

        hide(
            el.resultsContainer
        );

        show(
            el.emptyState
        );
    }
        // ============================================================
    // NAVIGATION
    // ============================================================

    function isMobile() {
        return window.matchMedia(
            "(max-width: 980px)"
        ).matches;
    }


    function openSidebar() {
        if (!el.sidebar) {
            return;
        }


        el.sidebar.classList.add(
            "open"
        );


        show(
            el.sidebarOverlay
        );


        document.body.classList.add(
            "nav-open"
        );
    }


    function closeSidebar() {
        if (!el.sidebar) {
            return;
        }


        el.sidebar.classList.remove(
            "open"
        );


        hide(
            el.sidebarOverlay
        );


        document.body.classList.remove(
            "nav-open"
        );
    }


    function setActiveNavigation(
        targetId
    ) {
        document
            .querySelectorAll(
                ".nav-item"
            )
            .forEach(
                (button) => {

                    button.classList.toggle(
                        "active",

                        button
                            .dataset
                            .target ===
                            targetId
                    );
                }
            );
    }


    function scrollToSection(
        targetId
    ) {
        const target =
            byId(
                targetId
            );

        if (!target) {
            return;
        }


        setActiveNavigation(
            targetId
        );


        target.scrollIntoView(
            {
                behavior:
                    "smooth",

                block:
                    "start"
            }
        );


        if (isMobile()) {
            closeSidebar();
        }
    }


    function setupNavigation() {
        document
            .querySelectorAll(
                ".nav-item"
            )
            .forEach(
                (button) => {

                    button.addEventListener(
                        "click",
                        () => {

                            const targetId =
                                button
                                    .dataset
                                    .target;


                            if (
                                targetId ===
                                    "analyst-intelligence" &&
                                !state.currentDecision
                            ) {
                                showToast(
                                    "Analyze a VIN first",
                                    (
                                        "Ask Analyst becomes available " +
                                        "after AutoPulse builds a vehicle report."
                                    ),
                                    "info"
                                );

                                scrollToSection(
                                    "command-center"
                                );

                                return;
                            }


                            scrollToSection(
                                targetId
                            );
                        }
                    );
                }
            );


        el.sidebarToggleButton
            ?.addEventListener(
                "click",
                openSidebar
            );


        el.sidebarCloseButton
            ?.addEventListener(
                "click",
                closeSidebar
            );


        el.sidebarOverlay
            ?.addEventListener(
                "click",
                closeSidebar
            );


        document.addEventListener(
            "keydown",
            (event) => {

                if (
                    event.key ===
                    "Escape"
                ) {
                    closeSidebar();
                }
            }
        );


        if (
            "IntersectionObserver"
            in window
        ) {
            const sections = [
                "command-center",
                "safety-intelligence",
                "trend-intelligence",
                "recall-intelligence",
                "analyst-intelligence"
            ]
                .map(byId)
                .filter(Boolean);


            const observer =
                new IntersectionObserver(
                    (entries) => {

                        const visible =
                            entries
                                .filter(
                                    (entry) =>
                                        entry
                                            .isIntersecting
                                )
                                .sort(
                                    (a, b) =>
                                        b
                                            .intersectionRatio -
                                        a
                                            .intersectionRatio
                                );


                        if (
                            visible.length
                        ) {
                            setActiveNavigation(
                                visible[
                                    0
                                ]
                                    .target
                                    .id
                            );
                        }
                    },
                    {
                        rootMargin:
                            "-18% 0px -65% 0px",

                        threshold: [
                            0.05,
                            0.15,
                            0.35
                        ]
                    }
                );


            sections.forEach(
                (section) =>
                    observer.observe(
                        section
                    )
            );
        }
    }


    // ============================================================
    // RESOURCE LINKS
    // ============================================================

    function updateVehicleLinks(
        vin,
        vehicle = {}
    ) {
        const cleanVin =
            normalizeVin(
                vin
            );


        const year =
            vehicle.model_year ||
            "";


        const make =
            vehicle.make ||
            "";


        const model =
            vehicle.model ||
            "";


        // vPIC supports a real VIN-specific decoder result URL.
        // Model year is included when AutoPulse has it because NHTSA
        // recommends supplying it to improve decode accuracy.
        if (
            el.nhtsaVinLink
        ) {
            el.nhtsaVinLink.href =
                cleanVin
                    ? (
                        "https://vpic.nhtsa.dot.gov/" +
                        "decoder/VinDecoder" +
                        `?ModelYear=${encodeURIComponent(
                            year
                        )}` +
                        `&VIN=${encodeURIComponent(
                            cleanVin
                        )}`
                    )
                    : (
                        "https://vpic.nhtsa.dot.gov/" +
                        "decoder/"
                    );


            el.nhtsaVinLink.title =
                cleanVin
                    ? (
                        "Open NHTSA vPIC decode results " +
                        `for ${cleanVin}`
                    )
                    : "Open the NHTSA VIN Decoder";
        }


        // NHTSA's recalls experience accepts VIN in the query string.
        // This is different from AutoPulse model-year recall evidence:
        // the external lookup is for VIN-specific unrepaired recalls.
        if (
            el.nhtsaRecallLink
        ) {
            el.nhtsaRecallLink.href =
                cleanVin
                    ? (
                        "https://www.nhtsa.gov/recalls" +
                        `?vin=${encodeURIComponent(
                            cleanVin
                        )}`
                    )
                    : "https://www.nhtsa.gov/recalls";


            el.nhtsaRecallLink.title =
                cleanVin
                    ? (
                        "Check NHTSA VIN-specific open recalls " +
                        `for ${cleanVin}`
                    )
                    : "Open NHTSA recall lookup";
        }


        // NHTSA vehicle detail pages are indexed by model year,
        // make and model. NCAP is not inherently VIN-specific, so
        // this intentionally opens the exact decoded vehicle model
        // rather than pretending a VIN-level crash-test rating exists.
        if (
            el.nhtsaRatingsLink
        ) {
            const hasVehicleIdentity =
                Boolean(
                    year &&
                    make &&
                    model
                );


            el.nhtsaRatingsLink.href =
                hasVehicleIdentity
                    ? (
                        "https://www.nhtsa.gov/vehicle/" +
                        `${encodeURIComponent(year)}/` +
                        `${encodeURIComponent(make)}/` +
                        `${encodeURIComponent(model)}`
                    )
                    : "https://www.nhtsa.gov/ratings";


            el.nhtsaRatingsLink.title =
                hasVehicleIdentity
                    ? (
                        "Open NHTSA vehicle safety information " +
                        `for ${year} ${make} ${model}`
                    )
                    : "Open NHTSA safety ratings";
        }


        // CARFAX uses the VIN to identify the requested vehicle.
        // CARFAX may still require sign-in or purchase before the
        // complete licensed history report is displayed.
        if (
            el.carfaxReportLink
        ) {
            el.carfaxReportLink.href =
                cleanVin
                    ? (
                        "https://www.carfax.com/" +
                        "VehicleHistory/p/Report.cfx" +
                        `?vin=${encodeURIComponent(
                            cleanVin
                        )}`
                    )
                    : (
                        "https://www.carfax.com/" +
                        "vehicle-history-reports/"
                    );


            el.carfaxReportLink.title =
                cleanVin
                    ? (
                        "Open the CARFAX lookup flow " +
                        `for ${cleanVin}`
                    )
                    : "Open CARFAX vehicle history reports";
        }


        [
            el.nhtsaVinLink,
            el.nhtsaRecallLink,
            el.nhtsaRatingsLink,
            el.carfaxReportLink
        ].forEach(
            (link) => {

                if (!link) {
                    return;
                }


                if (cleanVin) {
                    link.dataset.vin =
                        cleanVin;

                } else {
                    delete link.dataset.vin;
                }
            }
        );
    }


    // ============================================================
    // ASK AUTOPULSE ANALYST
    // ============================================================

    function analystSuggestionButtons() {
        return [
            ...document.querySelectorAll(
                "[data-analyst-question]"
            )
        ];
    }


    function setAnalystStatus(
        message,
        status = ""
    ) {
        if (
            !el.analystStatus
        ) {
            return;
        }


        setText(
            el.analystStatus,
            message,
            ""
        );


        if (status) {
            el.analystStatus.dataset.state =
                status;

        } else {
            delete el.analystStatus
                .dataset
                .state;
        }
    }
        function setAnalystControlsEnabled(
        enabled
    ) {
        const usable =
            Boolean(
                enabled &&
                !state.analystBusy
            );


        analystSuggestionButtons()
            .forEach(
                (button) => {
                    button.disabled =
                        !usable;
                }
            );


        if (
            el.analystQuestion
        ) {
            el.analystQuestion.disabled =
                !usable;
        }


        if (
            el.analystAskButton
        ) {
            el.analystAskButton.disabled =
                !usable;
        }
    }


    function getAnalystEvidenceLabel() {
        const availability =
            state.currentDecision
                ?.source_availability ||
            {};


        if (
            !state.currentDecision
        ) {
            return {
                text:
                    "Awaiting evidence",
                state:
                    "unavailable"
            };
        }


        const partial =
            availability
                .partial_report ===
                true;


        const supplementalGap =
            state.reportReady &&
            (
                !state.currentNcap ||
                !state.currentTrend
            );


        if (
            partial ||
            supplementalGap
        ) {
            return {
                text:
                    "Partial evidence · source gaps preserved",
                state:
                    "partial"
            };
        }


        if (
            !state.reportReady
        ) {
            return {
                text:
                    "Loading supporting evidence",
                state:
                    "partial"
            };
        }


        return {
            text:
                "Available evidence loaded",
            state:
                "complete"
        };
    }


    function updateAnalystContext() {
        if (
            el.analystVehicleLabel
        ) {
            setText(
                el.analystVehicleLabel,
                state.currentDecision
                    ? (
                        `${vehicleDisplayName(
                            state.currentVehicle ||
                            {}
                        )} · ${state.currentVin || "VIN unavailable"}`
                    )
                    : "Waiting for VIN analysis"
            );
        }


        const evidence =
            getAnalystEvidenceLabel();


        if (
            el.analystEvidenceStatus
        ) {
            setText(
                el.analystEvidenceStatus,
                evidence.text
            );


            el.analystEvidenceStatus
                .dataset
                .state =
                    evidence.state;
        }


        if (
            !state.currentDecision
        ) {
            setAnalystStatus(
                (
                    "Analyze a VIN, then choose a question " +
                    "or write your own."
                )
            );

            setAnalystControlsEnabled(
                false
            );

            return;
        }


        if (
            !state.reportReady
        ) {
            setAnalystStatus(
                (
                    "AutoPulse is still loading the supporting " +
                    "evidence for this VIN."
                ),
                "working"
            );

            setAnalystControlsEnabled(
                false
            );

            return;
        }


        setAnalystStatus(
            evidence.state ===
                "partial"
                ? (
                    "Ready · Ask Analyst will explain only the " +
                    "evidence that was successfully retrieved."
                )
                : (
                    "Ready · Ask a question about the active " +
                    "vehicle report."
                ),
            evidence.state ===
                "partial"
                ? "warning"
                : "ready"
        );


        setAnalystControlsEnabled(
            true
        );
    }


    function resetAnalystView() {
        state.reportReady =
            false;

        state.analystBusy =
            false;

        state.analystRequestId +=
            1;


        if (
            el.analystQuestion
        ) {
            el.analystQuestion.value =
                "";
        }


        if (
            el.analystResponse
        ) {
            el.analystResponse.textContent =
                "";

            delete el.analystResponse
                .dataset
                .state;

            hide(
                el.analystResponse
            );
        }


        updateAnalystContext();
    }


    function buildAnalystContext() {
        return {
            vin:
                state.currentVin,

            vehicle:
                state.currentVehicle,

            decision_report:
                state.currentDecision,

            ncap:
                state.currentNcap,

            trend:
                state.currentTrend,

            evidence_policy: {
                unavailable_is_zero:
                    false,

                instruction:
                    (
                        "Unavailable evidence must remain unavailable. " +
                        "Do not infer zero complaints, zero recalls, " +
                        "zero injuries, zero deaths or a favorable " +
                        "risk result from a failed or missing source."
                    )
            }
        };
    }


    function setAnalystBusy(
        busy
    ) {
        state.analystBusy =
            busy;


        if (
            el.analystAskButton
        ) {
            if (
                !el
                    .analystAskButton
                    .dataset
                    .defaultText
            ) {
                el
                    .analystAskButton
                    .dataset
                    .defaultText =
                        el
                            .analystAskButton
                            .textContent
                            .trim();
            }


            el.analystAskButton.textContent =
                busy
                    ? "Analyzing..."
                    : el
                        .analystAskButton
                        .dataset
                        .defaultText;
        }


        setAnalystControlsEnabled(
            state.reportReady
        );
    }


    // ============================================================
    // ANALYST RESPONSE FORMATTING
    // ============================================================

    function appendAnalystInlineFormatting(
        parent,
        text
    ) {
        const value =
            String(
                text || ""
            );


        const boldPattern =
            /\*\*(.+?)\*\*/g;


        let cursor =
            0;


        let match;


        while (
            (
                match =
                    boldPattern.exec(
                        value
                    )
            ) !== null
        ) {
            if (
                match.index >
                cursor
            ) {
                parent.appendChild(
                    document.createTextNode(
                        value.slice(
                            cursor,
                            match.index
                        )
                    )
                );
            }


            const strong =
                document.createElement(
                    "strong"
                );


            strong.textContent =
                match[
                    1
                ];


            parent.appendChild(
                strong
            );


            cursor =
                match.index +
                match[
                    0
                ].length;
        }


        if (
            cursor <
            value.length
        ) {
            parent.appendChild(
                document.createTextNode(
                    value.slice(
                        cursor
                    )
                )
            );
        }
    }


    function renderAnalystAnswer(
        answer
    ) {
        if (
            !el.analystResponse
        ) {
            return;
        }


        clearNode(
            el.analystResponse
        );


        const lines =
            String(
                answer || ""
            )
                .replace(
                    /\r\n/g,
                    "\n"
                )
                .split(
                    "\n"
                );


        let activeList =
            null;


        let activeListType =
            null;


        function closeList() {
            activeList =
                null;

            activeListType =
                null;
        }


        function ensureList(
            type
        ) {
            if (
                activeList &&
                activeListType ===
                    type
            ) {
                return activeList;
            }


            closeList();


            activeList =
                document.createElement(
                    type
                );


            activeList.className =
                "analyst-response-list";


            activeListType =
                type;


            el.analystResponse
                .appendChild(
                    activeList
                );


            return activeList;
        }


        lines.forEach(
            (rawLine) => {

                const line =
                    rawLine.trim();


                if (!line) {
                    closeList();

                    return;
                }


                const markdownHeading =
                    line.match(
                        /^#{1,4}\s+(.+)$/
                    );


                const boldHeading =
                    line.match(
                        /^\*\*(.+?)\*\*:?\s*$/
                    );


                if (
                    markdownHeading ||
                    boldHeading
                ) {
                    closeList();


                    const heading =
                        document.createElement(
                            "h4"
                        );


                    heading.className =
                        "analyst-response-heading";


                    heading.textContent =
                        (
                            markdownHeading
                                ? markdownHeading[
                                    1
                                ]
                                : boldHeading[
                                    1
                                ]
                        )
                            .replace(
                                /:$/,
                                ""
                            )
                            .trim();


                    el.analystResponse
                        .appendChild(
                            heading
                        );


                    return;
                }


                const bullet =
                    line.match(
                        /^[-*]\s+(.+)$/
                    );


                if (bullet) {
                    const list =
                        ensureList(
                            "ul"
                        );


                    const item =
                        document.createElement(
                            "li"
                        );


                    appendAnalystInlineFormatting(
                        item,
                        bullet[
                            1
                        ]
                    );


                    list.appendChild(
                        item
                    );


                    return;
                }


                const numbered =
                    line.match(
                        /^\d+[.)]\s+(.+)$/
                    );


                if (numbered) {
                    const list =
                        ensureList(
                            "ol"
                        );


                    const item =
                        document.createElement(
                            "li"
                        );


                    appendAnalystInlineFormatting(
                        item,
                        numbered[
                            1
                        ]
                    );


                    list.appendChild(
                        item
                    );


                    return;
                }


                closeList();


                const paragraph =
                    document.createElement(
                        "p"
                    );


                appendAnalystInlineFormatting(
                    paragraph,
                    line
                );


                el.analystResponse
                    .appendChild(
                        paragraph
                    );
            }
        );


        if (
            !el.analystResponse
                .childNodes
                .length
        ) {
            const paragraph =
                document.createElement(
                    "p"
                );


            paragraph.textContent =
                "No analyst response was returned.";


            el.analystResponse
                .appendChild(
                    paragraph
                );
        }


        delete el.analystResponse
            .dataset
            .state;


        show(
            el.analystResponse
        );
    }


    async function askAnalyst(
        questionOverride = null
    ) {
        if (
            !state.currentVin ||
            !state.currentDecision
        ) {
            showToast(
                "Analyze a VIN first",
                (
                    "Ask Analyst needs an active AutoPulse " +
                    "vehicle report."
                ),
                "info"
            );

            scrollToSection(
                "command-center"
            );

            return;
        }


        if (
            !state.reportReady
        ) {
            showToast(
                "Report still loading",
                (
                    "Wait for AutoPulse to finish loading " +
                    "the supporting evidence."
                ),
                "info"
            );

            return;
        }


        const question =
            String(
                questionOverride ||
                el.analystQuestion
                    ?.value ||
                ""
            ).trim();


        if (!question) {
            setAnalystStatus(
                "Enter a question for Ask Analyst.",
                "warning"
            );

            el.analystQuestion
                ?.focus();

            return;
        }


        if (
            question.length >
            1200
        ) {
            setAnalystStatus(
                (
                    "Keep the question under " +
                    "1,200 characters."
                ),
                "warning"
            );

            return;
        }


        if (
            el.analystQuestion
        ) {
            el.analystQuestion.value =
                question;
        }


        const analystRequestId =
            ++state.analystRequestId;


        setAnalystBusy(
            true
        );


        setAnalystStatus(
            (
                "Analyzing the active VIN report without " +
                "filling gaps in unavailable evidence..."
            ),
            "working"
        );


        if (
            el.analystResponse
        ) {
            el.analystResponse.textContent =
                "";

            delete el.analystResponse
                .dataset
                .state;

            hide(
                el.analystResponse
            );
        }


        try {
            const payload =
                await fetchJson(
                    API.analyst,
                    {
                        timeout:
                            90000,

                        method:
                            "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                vin:
                                    state.currentVin,

                                question,

                                context:
                                    buildAnalystContext()
                            })
                    }
                );


            if (
                analystRequestId !==
                state.analystRequestId
            ) {
                return;
            }


            const answer =
                payload?.answer ||
                payload?.analysis ||
                payload?.response ||
                payload?.message;


            if (
                typeof answer !==
                    "string" ||
                !answer.trim()
            ) {
                throw new Error(
                    (
                        "Ask Analyst returned an empty response. " +
                        "Please retry."
                    )
                );
            }


            renderAnalystAnswer(
                answer.trim()
            );


            setAnalystStatus(
                (
                    "Analysis complete · grounded in the " +
                    "current AutoPulse evidence package."
                ),
                (
                    getAnalystEvidenceLabel()
                        .state ===
                        "partial"
                )
                    ? "warning"
                    : "ready"
            );

        } catch (
            error
        ) {
            if (
                analystRequestId !==
                state.analystRequestId
            ) {
                return;
            }


            const message =
                error?.message ||
                (
                    "Ask Analyst could not complete " +
                    "the request."
                );


            if (
                el.analystResponse
            ) {
                el.analystResponse.textContent =
                    (
                        "Ask Analyst is unavailable right now. " +
                        message
                    );

                el.analystResponse
                    .dataset
                    .state =
                        "error";

                show(
                    el.analystResponse
                );
            }


            setAnalystStatus(
                (
                    "Analyst service unavailable · the vehicle " +
                    "report itself is still usable."
                ),
                "error"
            );


            showToast(
                "Ask Analyst unavailable",
                message,
                "error"
            );


            console.error(
                "AutoPulse Analyst:",
                error
            );

        } finally {
            if (
                analystRequestId ===
                state.analystRequestId
            ) {
                setAnalystBusy(
                    false
                );
            }
        }
    }


    function setupAnalyst() {
        analystSuggestionButtons()
            .forEach(
                (button) => {

                    button.addEventListener(
                        "click",
                        () => {

                            const question =
                                button
                                    .dataset
                                    .analystQuestion ||
                                button
                                    .textContent
                                    .trim();


                            askAnalyst(
                                question
                            );
                        }
                    );
                }
            );


        el.analystAskButton
            ?.addEventListener(
                "click",
                () => askAnalyst()
            );


        el.analystQuestion
            ?.addEventListener(
                "keydown",
                (event) => {

                    if (
                        event.key ===
                            "Enter" &&
                        (
                            event.ctrlKey ||
                            event.metaKey
                        )
                    ) {
                        event.preventDefault();

                        askAnalyst();
                    }
                }
            );


        resetAnalystView();
    }
        // ============================================================
    // DECISION DRIVERS
    // ============================================================

    function renderDecisionDrivers(
        drivers
    ) {
        clearNode(
            el.decisionDrivers
        );


        if (
            !Array.isArray(
                drivers
            ) ||
            !drivers.length
        ) {
            el.decisionDrivers
                ?.appendChild(
                    createElement(
                        "li",
                        "",
                        (
                            "No additional evidence " +
                            "drivers were returned."
                        )
                    )
                );

            return;
        }


        drivers
            .slice(
                0,
                4
            )
            .forEach(
                (driver) => {

                    el.decisionDrivers
                        ?.appendChild(
                            createElement(
                                "li",
                                "",
                                driver
                            )
                        );
                }
            );
    }


    // ============================================================
    // REAL-WORLD ISSUE INTELLIGENCE
    // ============================================================

    function renderRealWorldIssues(
        issues,
        {
            complaintsAvailable =
                true,

            unavailableMessage =
                null
        } = {}
    ) {
        if (
            !el.realWorldIssueList
        ) {
            return;
        }


        clearNode(
            el.realWorldIssueList
        );


        if (
            !complaintsAvailable
        ) {
            el.realWorldIssueList
                .appendChild(
                    createElement(
                        "div",
                        (
                            "empty-inline " +
                            "source-unavailable-state"
                        ),
                        (
                            unavailableMessage ||
                            (
                                "Owner-report intelligence " +
                                "is temporarily unavailable " +
                                "because NHTSA complaint " +
                                "evidence could not be " +
                                "retrieved. This is not " +
                                "equivalent to zero complaints."
                            )
                        )
                    )
                );

            return;
        }


        if (
            !Array.isArray(
                issues
            ) ||
            !issues.length
        ) {
            el.realWorldIssueList
                .appendChild(
                    createElement(
                        "div",
                        "empty-inline",
                        (
                            "No concentrated owner-reported " +
                            "issue signal was identified in " +
                            "the available complaint evidence."
                        )
                    )
                );

            return;
        }


        issues
            .slice(
                0,
                5
            )
            .forEach(
                (item, index) => {

                    const card =
                        createElement(
                            "article",
                            "signal-row"
                        );


                    const rank =
                        createElement(
                            "span",
                            "signal-rank",
                            String(
                                index + 1
                            ).padStart(
                                2,
                                "0"
                            )
                        );


                    const main =
                        createElement(
                            "div",
                            "signal-main"
                        );


                    const issueName =
                        formatLabel(
                            item.issue_cluster ||
                            item.issue ||
                            item.component
                        );


                    main.appendChild(
                        createElement(
                            "strong",
                            "signal-name",
                            issueName
                        )
                    );


                    const complaintCount =
                        Number(
                            item
                                .complaint_mentions
                        ) || 0;


                    let context =
                        (
                            `${formatNumber(
                                complaintCount
                            )} complaint ${
                                complaintCount === 1
                                    ? "mention"
                                    : "mentions"
                            }`
                        );


                    if (
                        item
                            .complaint_mention_pct !==
                            null &&
                        item
                            .complaint_mention_pct !==
                            undefined
                    ) {
                        context +=
                            (
                                ` · ${formatDecimal(
                                    item
                                        .complaint_mention_pct,
                                    1
                                )}% of complaint records`
                            );
                    }


                    main.appendChild(
                        createElement(
                            "span",
                            "signal-context",
                            context
                        )
                    );


                    const evidence =
                        [];


                    if (
                        Number(
                            item
                                .crash_mentions
                        ) > 0
                    ) {
                        evidence.push(
                            (
                                `${formatNumber(
                                    item
                                        .crash_mentions
                                )} crash ${
                                    Number(
                                        item
                                            .crash_mentions
                                    ) === 1
                                        ? "mention"
                                        : "mentions"
                                }`
                            )
                        );
                    }


                    if (
                        Number(
                            item
                                .fire_mentions
                        ) > 0
                    ) {
                        evidence.push(
                            (
                                `${formatNumber(
                                    item
                                        .fire_mentions
                                )} fire ${
                                    Number(
                                        item
                                            .fire_mentions
                                    ) === 1
                                        ? "mention"
                                        : "mentions"
                                }`
                            )
                        );
                    }


                    if (
                        Number(
                            item
                                .reported_injuries
                        ) > 0
                    ) {
                        evidence.push(
                            (
                                `${formatNumber(
                                    item
                                        .reported_injuries
                                )} injuries`
                            )
                        );
                    }


                    if (
                        Number(
                            item
                                .reported_deaths
                        ) > 0
                    ) {
                        evidence.push(
                            (
                                `${formatNumber(
                                    item
                                        .reported_deaths
                                )} deaths`
                            )
                        );
                    }


                    if (
                        Number(
                            item
                                .related_recall_campaigns
                        ) > 0
                    ) {
                        evidence.push(
                            (
                                `${formatNumber(
                                    item
                                        .related_recall_campaigns
                                )} related ${
                                    Number(
                                        item
                                            .related_recall_campaigns
                                    ) === 1
                                        ? "recall"
                                        : "recalls"
                                }`
                            )
                        );
                    }


                    if (
                        item.recent_trend &&
                        item.recent_trend !==
                            "INSUFFICIENT_BASELINE"
                    ) {
                        evidence.push(
                            (
                                `Trend: ${formatLabel(
                                    item
                                        .recent_trend
                                )}`
                            )
                        );
                    }


                    if (
                        evidence.length
                    ) {
                        main.appendChild(
                            createElement(
                                "span",
                                "signal-evidence",
                                evidence.join(
                                    " · "
                                )
                            )
                        );
                    }


                    const severity =
                        createElement(
                            "span",
                            "signal-severity",
                            formatLabel(
                                item
                                    .severity_signal ||
                                "Observed"
                            )
                        );


                    severity
                        .dataset
                        .severity =
                            String(
                                item
                                    .severity_signal ||
                                "observed"
                            )
                                .toLowerCase();


                    card.append(
                        rank,
                        main,
                        severity
                    );


                    el
                        .realWorldIssueList
                        .appendChild(
                            card
                        );
                }
            );
    }


    // ============================================================
    // RECALL INTELLIGENCE
    // ============================================================

    function calculateRecallAttention(
        recalls
    ) {
        if (
            !Array.isArray(
                recalls
            )
        ) {
            return 0;
        }


        const priorityTerms = [
            "fire",
            "catch fire",
            "thermal",
            "crash",
            "injury",
            "injuries",
            "death",
            "fatal",
            "stop drive",
            "stop driving",
            "park outside",
            "do not drive"
        ];


        return recalls.reduce(
            (
                count,
                recall
            ) => {

                const text = [
                    recall.subject,
                    recall.component,
                    recall.summary,
                    recall.consequence,
                    recall.remedy
                ]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase();


                const priority =
                    priorityTerms.some(
                        (term) =>
                            text.includes(
                                term
                            )
                    );


                return (
                    count +
                    (
                        priority
                            ? 1
                            : 0
                    )
                );
            },
            0
        );
    }


    function renderRecalls(
        recalls,
        recallCount,
        intelligence = {}
    ) {
        const records =
            Array.isArray(
                recalls
            )
                ? recalls
                : [];


        const backendPriority =
            Number(
                intelligence
                    .urgent_attention_campaigns
            );


        const urgentCount =
            Number.isFinite(
                backendPriority
            )
                ? backendPriority
                : calculateRecallAttention(
                    records
                );


        setText(
            el.recallUrgency,
            urgentCount > 0
                ? (
                    `${urgentCount} priority ${
                        urgentCount === 1
                            ? "cue"
                            : "cues"
                    }`
                )
                : "Standard review"
        );


        if (
            el.recallUrgency
        ) {
            el.recallUrgency
                .dataset
                .state =
                    urgentCount > 0
                        ? "attention"
                        : "standard";
        }


        const recallsAvailable =
            hasMetricValue(
                recallCount
            );


        setText(
            el.recallBadge,
            recallsAvailable
                ? (
                    `${formatNumber(
                        recallCount
                    )} ${
                        Number(
                            recallCount
                        ) === 1
                            ? "recall"
                            : "recalls"
                    }`
                )
                : "Recalls unavailable"
        );


        setText(
            el.recallScopeLabel,
            formatLabel(
                intelligence.scope ||
                "MODEL_YEAR_CAMPAIGN_EVIDENCE"
            )
        );


        setText(
            el.recallScopeNote,
            intelligence.note ||
            (
                "These campaigns are associated " +
                "with the selected make, model " +
                "and model year. They do not " +
                "establish whether this individual " +
                "VIN has an open or completed recall."
            )
        );


        if (
            !el.recallList
        ) {
            return;
        }


        clearNode(
            el.recallList
        );


        if (
            !records.length
        ) {
            el.recallList.appendChild(
                createElement(
                    "div",
                    "empty-inline",
                    !recallsAvailable
                        ? (
                            "Recall intelligence is temporarily " +
                            "unavailable. AutoPulse does not " +
                            "interpret an unavailable recall " +
                            "source as zero recalls."
                        )
                        : (
                            Number(
                                recallCount
                            ) > 0
                                ? (
                                    "Recall campaigns were reported, " +
                                    "but detailed campaign records " +
                                    "were not returned."
                                )
                                : (
                                    "No recall campaigns were returned " +
                                    "for this vehicle configuration."
                                )
                        )
                )
            );

            return;
        }


        records.forEach(
            (
                recall,
                index
            ) => {

                const card =
                    createElement(
                        "article",
                        "recall-card"
                    );


                const top =
                    createElement(
                        "div",
                        "recall-card-top"
                    );


                const indexBadge =
                    createElement(
                        "span",
                        "recall-index",
                        String(
                            index + 1
                        ).padStart(
                            2,
                            "0"
                        )
                    );


                const heading =
                    createElement(
                        "div",
                        "recall-heading"
                    );


                heading.appendChild(
                    createElement(
                        "h3",
                        "",
                        recall.subject ||
                        recall.component ||
                        "NHTSA recall campaign"
                    )
                );


                const meta =
                    createElement(
                        "div",
                        "recall-meta"
                    );


                if (
                    recall
                        .campaign_number
                ) {
                    meta.appendChild(
                        createElement(
                            "span",
                            "",
                            (
                                `Campaign ${
                                    recall
                                        .campaign_number
                                }`
                            )
                        )
                    );
                }


                if (
                    recall
                        .report_received_date
                ) {
                    meta.appendChild(
                        createElement(
                            "span",
                            "",
                            recall
                                .report_received_date
                        )
                    );
                }


                heading.appendChild(
                    meta
                );


                top.append(
                    indexBadge,
                    heading
                );


                card.appendChild(
                    top
                );


                if (
                    recall.component
                ) {
                    const component =
                        createElement(
                            "div",
                            "recall-component"
                        );


                    component.append(
                        createElement(
                            "span",
                            "",
                            "Component"
                        ),

                        createElement(
                            "strong",
                            "",
                            formatLabel(
                                recall.component
                            )
                        )
                    );


                    card.appendChild(
                        component
                    );
                }


                const body =
                    createElement(
                        "div",
                        "recall-body"
                    );


                [
                    [
                        "Summary",
                        recall.summary
                    ],

                    [
                        "Consequence",
                        recall.consequence
                    ],

                    [
                        "Remedy",
                        recall.remedy
                    ]
                ].forEach(
                    (
                        [
                            label,
                            value
                        ]
                    ) => {

                        if (
                            !value
                        ) {
                            return;
                        }


                        const block =
                            createElement(
                                "div",
                                "recall-detail"
                            );


                        block.append(
                            createElement(
                                "strong",
                                "",
                                label
                            ),

                            createElement(
                                "p",
                                "",
                                value
                            )
                        );


                        body.appendChild(
                            block
                        );
                    }
                );


                card.appendChild(
                    body
                );


                el.recallList
                    .appendChild(
                        card
                    );
            }
        );
    }
        // ============================================================
    // MAIN DECISION RENDER
    // ============================================================

    function renderDecision(
        payload
    ) {
        state.currentDecision =
            payload;


        const vehicle =
            payload?.vehicle ||
            {};


        const vin =
            payload?.vin ||
            {};


        const decision =
            payload?.decision ||
            {};


        const safety =
            payload
                ?.safety_evidence ||
            {};


        const complaintSource =
            getSourceState(
                payload,
                "complaints"
            );


        const recallSource =
            getSourceState(
                payload,
                "recalls"
            );


        const sourceAvailability =
            payload
                ?.source_availability ||
            {};


        const partial =
            Boolean(
                sourceAvailability
                    .partial_report
            );


        const riskAvailable =
            (
                decision
                    .risk_score_available !==
                    false
            ) &&
            hasMetricValue(
                decision
                    .autopulse_risk_score
            );


        state.currentVehicle =
            vehicle;


        state.currentVin =
            vin.vin ||
            null;


        setText(
            el.vehicleTitle,
            vehicleDisplayName(
                vehicle
            )
        );


        const subtitle = [
            vin.vin
                ? (
                    `VIN ${
                        vin.vin
                    }`
                )
                : null,

            vin.manufacturer
        ]
            .filter(Boolean)
            .join(" · ");


        setText(
            el.vehicleSubtitle,
            subtitle,
            "VIN intelligence report"
        );


        setText(
            el.vehicleTypeBadge,
            vin.vehicle_type ||
            vin.body_class ||
            "Vehicle"
        );


        setText(
            el.fuelTypeBadge,
            vin.fuel_type ||
            "Fuel —"
        );


        setText(
            el.confidenceBadge,
            riskAvailable
                ? (
                    decision
                        .evidence_confidence
                        ? (
                            `Evidence ${
                                formatLabel(
                                    decision
                                        .evidence_confidence
                                )
                            }`
                        )
                        : "Evidence —"
                )
                : "Evidence incomplete"
        );


        setText(
            el.sourceAvailabilityBadge,
            partial
                ? "Partial evidence"
                : "Sources live"
        );


        if (
            el.sourceAvailabilityBadge
        ) {
            el
                .sourceAvailabilityBadge
                .dataset
                .state =
                    partial
                        ? "partial"
                        : "live";
        }


        const score =
            riskAvailable
                ? Number(
                    decision
                        .autopulse_risk_score
                )
                : null;


        setText(
            el.riskScore,
            (
                riskAvailable &&
                Number.isFinite(
                    score
                )
            )
                ? formatDecimal(
                    score,
                    1
                )
                : "—"
        );


        if (
            el.riskGauge
        ) {
            el.riskGauge
                .style
                .setProperty(
                    "--score",
                    (
                        riskAvailable &&
                        Number.isFinite(
                            score
                        )
                    )
                        ? clamp(
                            score,
                            0,
                            100
                        )
                        : 0
                );


            el.riskGauge
                .dataset
                .level =
                    riskAvailable
                        ? String(
                            decision
                                .attention_level ||
                            ""
                        ).toLowerCase()
                        : "unavailable";


            el.riskGauge
                .classList
                .toggle(
                    "risk-withheld",
                    !riskAvailable
                );
        }


        setText(
            el.attentionLevel,
            riskAvailable
                ? decision
                    .attention_level
                : "Risk signal withheld"
        );


        if (
            el.attentionLevel
        ) {
            el.attentionLevel
                .dataset
                .level =
                    riskAvailable
                        ? String(
                            decision
                                .attention_level ||
                            ""
                        ).toLowerCase()
                        : "unavailable";
        }


        setText(
            el.ownershipDecision,
            decision
                .ownership_decision ||
            (
                riskAvailable
                    ? "—"
                    : (
                        "INSUFFICIENT " +
                        "SOURCE COVERAGE"
                    )
            )
        );


        setText(
            el.ownershipRecommendation,
            decision
                .recommendation ||
            (
                riskAvailable
                    ? (
                        "No recommendation " +
                        "was returned."
                    )
                    : (
                        "AutoPulse withheld the risk " +
                        "signal because one or more " +
                        "core NHTSA evidence sources " +
                        "were unavailable. Unavailable " +
                        "evidence is not treated as zero."
                    )
            )
        );


        renderDecisionDrivers(
            payload
                ?.why_this_score ||
            []
        );


        setText(
            el.identityMake,
            vehicle.make
        );


        setText(
            el.identityModel,
            vehicle.model
        );


        setText(
            el.identityYear,
            vehicle.model_year
        );


        setText(
            el.identityBody,
            vin.body_class
        );


        setText(
            el.identityDrive,
            vin.drive_type
        );


        setText(
            el.identityOrigin,
            vin.plant_country
        );


        setText(
            el.complaintCount,
            metricText(
                safety.complaints,
                complaintSource
                    .available
            )
        );


        setText(
            el.recallCount,
            metricText(
                safety.recalls,
                recallSource
                    .available
            )
        );


        setText(
            el.crashCount,
            metricText(
                safety
                    .crash_complaints,
                complaintSource
                    .available
            )
        );


        setText(
            el.fireCount,
            metricText(
                safety
                    .fire_complaints,
                complaintSource
                    .available
            )
        );


        setText(
            el.injuryCount,
            metricText(
                safety
                    .reported_injuries,
                complaintSource
                    .available
            )
        );


        setText(
            el.deathCount,
            metricText(
                safety
                    .reported_deaths,
                complaintSource
                    .available
            )
        );


        renderRealWorldIssues(
            payload
                ?.real_world_issue_intelligence ||
            [],
            {
                complaintsAvailable:
                    complaintSource
                        .available,

                unavailableMessage:
                    payload
                        ?.issue_metric_note ||
                    complaintSource
                        .message
            }
        );


        renderRecalls(
            payload
                ?.recall_details ||
            [],

            recallSource
                .available
                ? safety.recalls
                : null,

            payload
                ?.recall_intelligence ||
            {}
        );


        updateVehicleLinks(
            vin.vin,
            vehicle
        );


        updateAnalystContext();
    }


    // ============================================================
    // NCAP
    // ============================================================

    function normalizeRating(
        value
    ) {
        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            return null;
        }


        const text =
            String(
                value
            ).trim();


        if (
            !text ||
            /^not rated$/i
                .test(
                    text
                )
        ) {
            return null;
        }


        return text;
    }


    function summarizeRating(
        rows,
        key
    ) {
        const values =
            rows
                .map(
                    (row) =>
                        normalizeRating(
                            row?.[
                                key
                            ]
                        )
                )
                .filter(Boolean);


        if (
            !values.length
        ) {
            return "—";
        }


        const unique =
            [
                ...new Set(
                    values
                )
            ];


        if (
            unique.length > 1
        ) {
            return "Varies";
        }


        const value =
            unique[
                0
            ];


        if (
            /^[0-5]$/.test(
                value
            )
        ) {
            return (
                `${value} / 5`
            );
        }


        return value;
    }


    function renderNcap(
        payload
    ) {
        state.currentNcap =
            payload;


        const rows =
            Array.isArray(
                payload?.ratings
            )
                ? payload.ratings
                : [];


        const testedVariants =
            Number(
                payload
                    ?.tested_variants
            ) ||
            rows.length;


        if (
            !rows.length
        ) {
            setText(
                el.ncapCoverage,
                payload
                    ?.coverage_note ||
                (
                    "No matching NHTSA " +
                    "NCAP-tested configuration " +
                    "was returned. This is not " +
                    "a zero-star rating."
                )
            );


            setText(
                el.ncapOverall,
                "—"
            );


            setText(
                el.ncapFront,
                "—"
            );


            setText(
                el.ncapSide,
                "—"
            );


            setText(
                el.ncapRollover,
                "—"
            );


            return;
        }


        setText(
            el.ncapCoverage,
            (
                `${testedVariants} tested ${
                    testedVariants === 1
                        ? "variant"
                        : "variants"
                }`
            )
        );


        setText(
            el.ncapOverall,
            summarizeRating(
                rows,
                "overall_rating"
            )
        );


        setText(
            el.ncapFront,
            summarizeRating(
                rows,
                "front_crash_rating"
            )
        );


        setText(
            el.ncapSide,
            summarizeRating(
                rows,
                "side_crash_rating"
            )
        );


        setText(
            el.ncapRollover,
            summarizeRating(
                rows,
                "rollover_rating"
            )
        );
    }


    function renderNcapUnavailable(
        message
    ) {
        state.currentNcap =
            null;


        setText(
            el.ncapCoverage,
            "NCAP temporarily unavailable"
        );


        [
            el.ncapOverall,
            el.ncapFront,
            el.ncapSide,
            el.ncapRollover
        ].forEach(
            (node) =>
                setText(
                    node,
                    "—"
                )
        );


        console.warn(
            "AutoPulse NCAP:",
            message
        );
    }


    // ============================================================
    // TREND INTELLIGENCE
    // ============================================================
        function humanizeTrendSignal(
        signal
    ) {
        const mapping = {
            SHARP_INCREASE:
                "Sharp increase",

            INCREASING:
                "Increasing",

            STABLE:
                "Stable",

            DECLINING:
                "Declining",

            INSUFFICIENT_HISTORY:
                "Limited history",

            UNAVAILABLE:
                "Unavailable"
        };


        return (
            mapping[
                signal
            ] ||
            formatLabel(
                signal
            )
        );
    }


    function renderTrendChart(
        timeline
    ) {
        if (
            !el.trendChart
        ) {
            return;
        }


        clearNode(
            el.trendChart
        );


        const rows =
            Array.isArray(
                timeline
            )
                ? timeline
                    .filter(
                        (item) =>
                            Number.isFinite(
                                Number(
                                    item?.year
                                )
                            )
                    )
                    .map(
                        (item) => ({
                            year:
                                Number(
                                    item.year
                                ),

                            complaints:
                                Number(
                                    item
                                        .complaints
                                ) || 0
                        })
                    )
                : [];


        if (
            !rows.length
        ) {
            el.trendChart
                .appendChild(
                    createElement(
                        "div",
                        "empty-inline",
                        (
                            "No dated complaint " +
                            "history was returned."
                        )
                    )
                );

            return;
        }


        const max =
            Math.max(
                1,
                ...rows.map(
                    (item) =>
                        item.complaints
                )
            );


        const chart =
            createElement(
                "div",
                "trend-bars"
            );


        rows.forEach(
            (item) => {

                const column =
                    createElement(
                        "div",
                        "trend-bar-column"
                    );


                const value =
                    createElement(
                        "strong",
                        "trend-bar-value",
                        formatNumber(
                            item.complaints
                        )
                    );


                const track =
                    createElement(
                        "div",
                        "trend-bar-track"
                    );


                const bar =
                    createElement(
                        "div",
                        "trend-bar"
                    );


                const height =
                    item.complaints === 0
                        ? 2
                        : Math.max(
                            6,
                            clamp(
                                (
                                    item.complaints /
                                    max
                                ) * 100,
                                0,
                                100
                            )
                        );


                bar.style.height =
                    `${height}%`;


                bar.title =
                    (
                        `${item.year}: ${
                            formatNumber(
                                item.complaints
                            )
                        } complaints`
                    );


                track.appendChild(
                    bar
                );


                const year =
                    createElement(
                        "span",
                        "trend-bar-year",
                        item.year
                    );


                column.append(
                    value,
                    track,
                    year
                );


                chart.appendChild(
                    column
                );
            }
        );


        el.trendChart
            .appendChild(
                chart
            );
    }


    function renderRecentIssues(
        issues
    ) {
        if (
            !el.recentIssueList
        ) {
            return;
        }


        clearNode(
            el.recentIssueList
        );


        if (
            !Array.isArray(
                issues
            ) ||
            !issues.length
        ) {
            el.recentIssueList
                .appendChild(
                    createElement(
                        "div",
                        (
                            "empty-inline " +
                            "compact"
                        ),
                        (
                            "No recent issue " +
                            "concentration was returned."
                        )
                    )
                );

            return;
        }


        issues
            .slice(
                0,
                4
            )
            .forEach(
                (item) => {

                    const row =
                        createElement(
                            "div",
                            "recent-issue-row"
                        );


                    row.append(
                        createElement(
                            "span",
                            "",
                            formatLabel(
                                item.component
                            )
                        ),

                        createElement(
                            "strong",
                            "",
                            formatNumber(
                                item.complaints
                            )
                        )
                    );


                    el.recentIssueList
                        .appendChild(
                            row
                        );
                }
            );
    }


    function renderTrend(
        payload
    ) {
        const unavailable =
            payload?.status ===
                "unavailable" ||
            payload
                ?.trend
                ?.signal ===
                "UNAVAILABLE";


        if (
            unavailable
        ) {
            renderTrendUnavailable(
                payload
                    ?.methodology_note ||
                payload
                    ?.source_availability
                    ?.complaints
                    ?.message ||
                (
                    "NHTSA complaint evidence " +
                    "is temporarily unavailable."
                )
            );

            return;
        }


        state.currentTrend =
            payload;


        const trend =
            payload?.trend ||
            {};


        const timeline =
            Array.isArray(
                payload?.timeline
            )
                ? payload.timeline
                : [];


        const recentComponents =
            Array.isArray(
                payload
                    ?.top_recent_components
            )
                ? payload
                    .top_recent_components
                : [];


        setText(
            el.trendSignalBadge,
            humanizeTrendSignal(
                trend.signal
            )
        );


        if (
            el.trendSignalBadge
        ) {
            el.trendSignalBadge
                .dataset
                .signal =
                    String(
                        trend.signal ||
                        ""
                    )
                        .toLowerCase();
        }


        setText(
            el.trendYear,
            hasMetricValue(
                trend
                    .latest_complete_year
            )
                ? trend
                    .latest_complete_year
                : "—"
        );


        setText(
            el.trendLatestCount,
            formatNumber(
                trend
                    .latest_year_complaints
            )
        );


        setText(
            el.trendBaseline,
            formatDecimal(
                trend
                    .baseline_average,
                1
            )
        );


        setText(
            el.trendAcceleration,
            hasMetricValue(
                trend
                    .complaint_acceleration_pct
            )
                ? formatPercent(
                    trend
                        .complaint_acceleration_pct,
                    1
                )
                : "Insufficient history"
        );


        const ytd =
            payload
                ?.current_ytd ||
            {};


        setText(
            el.trendYtdLabel,
            ytd.year
                ? `${ytd.year} YTD`
                : "Current YTD"
        );


        setText(
            el.trendYtdCount,
            formatNumber(
                ytd.complaints
            )
        );


        setText(
            el.trendYtdThrough,
            ytd.through_date
                ? (
                    `Through ${
                        ytd.through_date
                    } · excluded from headline trend`
                )
                : (
                    "Excluded from headline trend"
                )
        );


        setText(
            el.trendMethodologyNote,
            payload
                .methodology_note ||
            ytd.note ||
            (
                "Current-year activity is shown " +
                "separately from the complete-year " +
                "headline trend."
            )
        );


        renderTrendChart(
            timeline
        );


        renderRecentIssues(
            recentComponents
        );
    }


    function renderTrendUnavailable(
        message
    ) {
        state.currentTrend =
            null;


        setText(
            el.trendSignalBadge,
            "Unavailable"
        );


        if (
            el.trendSignalBadge
        ) {
            el.trendSignalBadge
                .dataset
                .signal =
                    "unavailable";
        }


        setText(
            el.trendYear,
            "—"
        );


        setText(
            el.trendLatestCount,
            "Unavailable"
        );


        setText(
            el.trendBaseline,
            "—"
        );


        setText(
            el.trendAcceleration,
            "—"
        );


        setText(
            el.trendYtdLabel,
            "Current YTD"
        );


        setText(
            el.trendYtdCount,
            "Unavailable"
        );


        setText(
            el.trendYtdThrough,
            "Source unavailable"
        );


        setText(
            el.trendMethodologyNote,
            message ||
            (
                "Complaint trend intelligence is " +
                "temporarily unavailable. AutoPulse " +
                "does not interpret unavailable " +
                "complaint evidence as zero complaints."
            )
        );


        if (
            el.trendChart
        ) {
            clearNode(
                el.trendChart
            );


            el.trendChart
                .appendChild(
                    createElement(
                        "div",
                        (
                            "empty-inline " +
                            "source-unavailable-state"
                        ),
                        (
                            "Complaint history is " +
                            "temporarily unavailable from " +
                            "NHTSA. This is a source-" +
                            "availability condition, not " +
                            "evidence of zero complaints."
                        )
                    )
                );
        }


        if (
            el.recentIssueList
        ) {
            clearNode(
                el.recentIssueList
            );


            el.recentIssueList
                .appendChild(
                    createElement(
                        "div",
                        (
                            "empty-inline compact " +
                            "source-unavailable-state"
                        ),
                        (
                            "Recent issue concentration " +
                            "cannot be calculated until " +
                            "complaint evidence is available."
                        )
                    )
                );
        }


        console.warn(
            "AutoPulse trends:",
            message
        );
    }


    // ============================================================
    // RESET SECONDARY CONTENT
    // ============================================================

    function resetSecondaryViews() {
        setText(
            el.ncapCoverage,
            (
                "Checking NHTSA " +
                "crash-test coverage..."
            )
        );


        setText(
            el.ncapOverall,
            "—"
        );


        setText(
            el.ncapFront,
            "—"
        );


        setText(
            el.ncapSide,
            "—"
        );


        setText(
            el.ncapRollover,
            "—"
        );


        setText(
            el.trendSignalBadge,
            "Loading"
        );


        setText(
            el.trendYear,
            "—"
        );


        setText(
            el.trendLatestCount,
            "—"
        );


        setText(
            el.trendBaseline,
            "—"
        );


        setText(
            el.trendAcceleration,
            "—"
        );


        setText(
            el.trendYtdLabel,
            "Current YTD"
        );


        setText(
            el.trendYtdCount,
            "—"
        );


        setText(
            el.trendYtdThrough,
            (
                "Excluded from " +
                "headline trend"
            )
        );


        setText(
            el.trendMethodologyNote,
            "Loading trend methodology..."
        );


        if (
            el.trendChart
        ) {
            clearNode(
                el.trendChart
            );


            el.trendChart
                .appendChild(
                    createElement(
                        "div",
                        "empty-inline",
                        (
                            "Loading complaint " +
                            "history..."
                        )
                    )
                );
        }


        if (
            el.recentIssueList
        ) {
            clearNode(
                el.recentIssueList
            );


            el.recentIssueList
                .appendChild(
                    createElement(
                        "div",
                        (
                            "empty-inline " +
                            "compact"
                        ),
                        (
                            "Loading recent issue " +
                            "concentration..."
                        )
                    )
                );
        }
    }


    // ============================================================
    // VIN ANALYSIS
    // ============================================================
        async function analyzeVin() {
        clearError();


        const vin =
            normalizeVin(
                el.vinInput
                    ?.value
            );


        const validationError =
            validateVin(
                vin
            );


        if (
            validationError
        ) {
            showError(
                validationError
            );


            el.vinInput
                ?.focus();


            return;
        }


        if (
            el.vinInput
        ) {
            el.vinInput.value =
                vin;
        }


        const requestId =
            ++state.requestId;


        setButtonBusy(
            true,
            "Analyzing..."
        );


        state.currentVin =
            null;

        state.currentVehicle =
            null;

        state.currentDecision =
            null;

        state.currentNcap =
            null;

        state.currentTrend =
            null;


        resetAnalystView();


        resetSecondaryViews();


        showLoading(
            (
                "Decoding VIN and building " +
                "the vehicle intelligence report..."
            )
        );


        try {

            // ----------------------------------------------------
            // 1. Primary VIN + safety decision
            // ----------------------------------------------------

            const decision =
                await fetchJson(
                    API.decisionByVin(
                        vin
                    ),
                    {
                        timeout:
                            75000
                    }
                );


            if (
                requestId !==
                state.requestId
            ) {
                return;
            }


            const vehicle =
                decision?.vehicle ||
                {};


            renderDecision(
                decision
            );


            showResults();


            updateLoading(
                (
                    "Loading crash-test ratings " +
                    "and complaint trends..."
                )
            );


            // ----------------------------------------------------
            // 2. NCAP + Trends load independently
            // ----------------------------------------------------

            const ncapRequest =
                (
                    vehicle.make &&
                    vehicle.model &&
                    vehicle.model_year
                )
                    ? fetchJson(
                        (
                            `${API.safetyRatings}?${
                                buildQuery({
                                    make:
                                        vehicle.make,

                                    model:
                                        vehicle.model,

                                    year:
                                        vehicle.model_year
                                })
                            }`
                        ),
                        {
                            timeout:
                                65000
                        }
                    )
                    : Promise.resolve(
                        null
                    );


            const trendRequest =
                (
                    vehicle.make &&
                    vehicle.model &&
                    vehicle.model_year
                )
                    ? fetchJson(
                        (
                            `${API.trends}?${
                                buildQuery({
                                    make:
                                        vehicle.make,

                                    model:
                                        vehicle.model,

                                    year:
                                        vehicle.model_year
                                })
                            }`
                        ),
                        {
                            timeout:
                                65000
                        }
                    )
                    : Promise.resolve(
                        null
                    );


            const [
                ncapResult,
                trendResult
            ] =
                await Promise.allSettled(
                    [
                        ncapRequest,
                        trendRequest
                    ]
                );


            if (
                requestId !==
                state.requestId
            ) {
                return;
            }


            // ----------------------------------------------------
            // NCAP
            // ----------------------------------------------------

            if (
                ncapResult.status ===
                    "fulfilled" &&
                ncapResult.value
            ) {
                renderNcap(
                    ncapResult.value
                );

            } else {
                renderNcapUnavailable(
                    ncapResult
                        .reason
                        ?.message ||
                    (
                        "NHTSA crash-test ratings " +
                        "were not available."
                    )
                );
            }


            // ----------------------------------------------------
            // Trends
            // ----------------------------------------------------

            if (
                trendResult.status ===
                    "fulfilled" &&
                trendResult.value
            ) {
                renderTrend(
                    trendResult.value
                );

            } else {
                renderTrendUnavailable(
                    trendResult
                        .reason
                        ?.message ||
                    (
                        "Complaint trend intelligence " +
                        "was not available."
                    )
                );
            }


            state.reportReady =
                true;


            updateAnalystContext();


            showToast(
                "Vehicle report ready",
                vehicleDisplayName(
                    vehicle
                ),
                "success"
            );


            window.setTimeout(
                () => {

                    const overview =
                        byId(
                            "vehicle-overview"
                        );


                    overview
                        ?.scrollIntoView(
                            {
                                behavior:
                                    "smooth",

                                block:
                                    "start"
                            }
                        );
                },
                100
            );

        } catch (
            error
        ) {

            resetAnalystView();


            showInitialState();


            const message =
                error?.message ||
                (
                    "Vehicle intelligence could " +
                    "not be retrieved. Please " +
                    "verify the VIN and retry."
                );


            showError(
                message
            );


            showToast(
                "Unable to build report",
                message,
                "error"
            );


            console.error(
                (
                    "AutoPulse " +
                    "VIN analysis:"
                ),
                error
            );

        } finally {

            if (
                requestId ===
                state.requestId
            ) {
                setButtonBusy(
                    false
                );
            }
        }
    }


    // ============================================================
    // HEALTH STATUS
    // ============================================================

    async function loadPlatformHealth() {
        const status =
            document.querySelector(
                ".platform-status"
            );


        const title =
            status
                ?.querySelector(
                    "strong"
                );


        const detail =
            status
                ?.querySelector(
                    "small"
                );


        if (
            !status ||
            !title ||
            !detail
        ) {
            return;
        }


        try {

            const payload =
                await fetchJson(
                    API.health,
                    {
                        timeout:
                            8000
                    }
                );


            status.classList.remove(
                "status-warning",
                "status-offline"
            );


            if (
                payload?.api ===
                    "healthy"
            ) {

                title.textContent =
                    "Platform Online";


                if (
                    payload
                        ?.database ===
                        "available"
                ) {
                    detail.textContent =
                        (
                            "NHTSA + database " +
                            "services available"
                        );

                } else {
                    detail.textContent =
                        (
                            "NHTSA live · " +
                            "database unavailable"
                        );


                    status.classList.add(
                        "status-warning"
                    );
                }

            } else {

                title.textContent =
                    (
                        "Platform status " +
                        "unknown"
                    );


                detail.textContent =
                    (
                        "Health response " +
                        "incomplete"
                    );


                status.classList.add(
                    "status-warning"
                );
            }

        } catch (
            error
        ) {

            title.textContent =
                "Platform Unavailable";


            detail.textContent =
                (
                    "Unable to reach " +
                    "AutoPulse API"
                );


            status.classList.add(
                "status-offline"
            );
        }
    }


    // ============================================================
    // INPUT BEHAVIOR
    // ============================================================

    function setupVinInput() {
        if (
            !el.vinInput
        ) {
            return;
        }


        el.vinInput.addEventListener(
            "input",
            () => {

                const normalized =
                    normalizeVin(
                        el
                            .vinInput
                            .value
                    );


                if (
                    el.vinInput.value !==
                    normalized
                ) {
                    el.vinInput.value =
                        normalized;
                }


                clearError();
            }
        );


        el.vinInput.addEventListener(
            "keydown",
            (event) => {

                if (
                    event.key ===
                    "Enter"
                ) {
                    event.preventDefault();

                    analyzeVin();
                }
            }
        );
    }


    // ============================================================
    // BUTTON BINDINGS
    // ============================================================

    function bindActions() {
        el.vinSearchButton
            ?.addEventListener(
                "click",
                analyzeVin
            );
    }


    // ============================================================
    // STARTUP
    // ============================================================

    function initialize() {
        cacheElements();

        setupNavigation();

        setupAnalyst();

        setupVinInput();

        bindActions();

        loadPlatformHealth();


        console.info(
            (
                "AutoPulse executive " +
                "frontend initialized."
            )
        );
    }


    if (
        document.readyState ===
        "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initialize,
            {
                once: true
            }
        );

    } else {
        initialize();
    }

})();