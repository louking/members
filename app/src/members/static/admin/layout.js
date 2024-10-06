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