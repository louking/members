// if a session expires while an admin page is open, its ajax/rest calls (e.g. datatables editor,
// or a page's own $.get()/$.post() buttons) start getting 401 json back instead of data.
// none of those call sites have their own 401 handling, and most don't wire up a jquery ajax
// failure handler at all, so the click/action would otherwise just silently do nothing.
// catch it here once, globally, and send the browser to the login page -- 'next' brings the user
// back to the page they were on once they reauthenticate, the same as a direct page navigation
// would via auth_required().
$(document).ajaxError(function(event, jqXHR) {
    if (jqXHR.status === 401) {
        window.location.href = '/account/login?next=' + encodeURIComponent(window.location.pathname + window.location.search);
    }
});

$( function() {
    $( "#navigation>ul").addClass("sm sm-blue");
    $( "#navigation>ul" ).smartmenus({
			subMenusSubOffsetX: 1,
			subMenusSubOffsetY: -8
    });

    // all navbar links which are not on this site (i.e., don't start with '/') open in new tab
    $( '.navbar a' ).not('[href^="/"]').attr('target', '_blank');

    // register interest group for all links
    register_group('interest', '#metanav-select-interest', 'a' );
});

// a[hreflang|='en']