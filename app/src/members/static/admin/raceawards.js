/**
 * raceawards.js - scripts for race awards admin page
 */

var divisions_rendered = false;
let awards_mutex = new MutexPromise('awards-table-update', {timeout: 10000})
let current_note_icon = null;

// from https://stackoverflow.com/questions/13627308/add-st-nd-rd-and-th-ordinal-suffix-to-a-number#comment119230834_57518703
function nth(n){return["st","nd","rd"][(((n<0?-n:n)+90)%100-10)%10-1]||"th"}

function updateawards() {
    let interest = $('#metanav-select-interest').val();
    let url = `/admin/${interest}/_raceawards/rest`;
    let urlparams = allUrlParams();
    urlparams['event_id'] = $('#events').val();
    urlparams['need_divisions'] = !divisions_rendered;

    return awards_mutex.promise()
        .then(function(mutex) {
            mutex.lock();
            let interest = $('#metanav-select-interest').val();
            let urlparams = allUrlParams();
            urlparams['event_id'] = $('#events').val();
            urlparams['need_divisions'] = !divisions_rendered;
            let url = `/admin/${interest}/_raceawards/rest` + '?' + setParams(urlparams);

            return $.get(url)
        })
        .then(function( json ) {
            if (json.error) {
                showerrorpopup(json.error);

            } else {
                // create table from json response
                // render divisions if first time through
                if (!divisions_rendered) {
                    // clear any leftover stuff first
                    $('#awards-table').empty();
                    for (let i=0; i<json.data.divisions.length; i++) {
                        let divrowdata = json.data.divisions[i];
                        let $divrow = $('<div class="awards-row"></div>');
                        $('#awards-table').append($divrow);
                        for (let j=0; j<divrowdata.length; j++) {
                            let divdata = divrowdata[j];
                            if (divdata==null) continue;

                            let $divgroup = $('<div class="awards-group"></div>');
                            $divrow.append($divgroup);
                            for (let place=1; place<=divdata.num_awards; place++) {
                                let $divcell = $(`<div id='${divdata.rsu_div_id}-${place}-cell' class='awards-cell'>`);
                                $divgroup.append($divcell);

                                let $checkarea = $(`<span class='awards-checkarea' div_id=${divdata.div_id}>`);
                                let $checkbox = $(`<i class='icon unchecked-circle awards-checkbox'>`);

                                let $divaward = $(`<div id='${divdata.rsu_div_id}-${place}-award' class='awards-award'>` +
                                                  `<p class='awards-header'>${place}${nth(place)} ${divdata.name}` + 
                                                  //   '<span style="float: right">' +
                                                  //   `<i id='${divdata.rsu_div_id}-${place}-toggle' class="fas fa-toggle-off" " aria-hidden="true"></i>` +
                                                  //   ` <i id='${divdata.rsu_div_id}-${place}-notes' class="fas fa-edit" aria-hidden="true"></i>` +
                                                  //   '</span>' +
                                                  `</p>` +
                                                  `<p id='${divdata.rsu_div_id}-${place}'></p>` + 
                                                  `</div>`
                                                );
                                
                                $checkarea.append($checkbox, $divaward);

                                let $notesspan = $('<span class="awards-notes-span">');
                                let $notes = $(`<i class='icon awards-notes add-comment'>`);
                                $notesspan.append($notes);

                                $divcell.append($checkarea, $notesspan);
                            }
                        }
                    }

                    // divisions are rendered
                    divisions_rendered = true;

                    // now we can create the click handlers
                    $('.awards-checkarea').click(toggle_picked_up);
                    $('.awards-notes').click(popup_note_dialog);
                    $('.awards-notes').tooltip();

                }

                // fill in awards
                for (let i=0; i<json.data.awards.length; i++) {
                    let award = json.data.awards[i];
                    let winner = `<span class='awards-bib'>${award.bib}</span>&ensp;<span class='awards-name'>${award.name}</span>`;
                    let $winner = $(winner);
                    let $award = $(`#${award.rsu_div_id}-${award.place}`);
                    $award.html($winner);
                    $award.closest('.awards-cell').attr('awardee_id', award.awardee_id);

                    let $cell = $award.closest('.awards-cell');

                    let $checkbox = $cell.find('.awards-checkbox');
                    if (award.picked_up) {
                        $cell.addClass('picked_up');
                        $checkbox.removeClass('unchecked-circle');
                        $checkbox.addClass('checked-circle');
                    } else {
                        $cell.removeClass('picked_up');
                        $checkbox.removeClass('checked-circle');
                        $checkbox.addClass('unchecked-circle');
                    }

                    if (award.prev_picked_up) {
                        $cell.addClass('prev_picked_up');
                    } else {
                        $cell.removeClass('prev_picked_up');
                    }

                    let $notes = $cell.find('.awards-notes');
                    if (award.notes) {
                        $notes.removeClass('add-comment');
                        $notes.addClass('insert-comment');
                        $notes.attr('title', award.notes);
                    } else {
                        $notes.removeClass('insert-comment');
                        $notes.addClass('add-comment');
                        $notes.removeAttr('title');
                    }
                }
            }
            awards_mutex.unlock();
        })
        .catch(function(e){
            // console.log('releasing lock due to exception');
            awards_mutex.unlock();
            throw e;
        });

}

function start_award_updates() {
    updateawards();
    let update_interval = setInterval(function() {
        updateawards();
    }, AWARDS_POLL_PERIOD*1000); // AWARDS_POLL_PERIOD is in seconds

    return update_interval
}

function stop_award_updates(interval) {
    clearInterval(interval);
}

function toggle_picked_up() {
    let $this = $(this);
    let $cell = $this.closest('.awards-cell');

    // don't do anything if no awardee
    if (!$cell.attr('awardee_id')) {
        return
    }

    return awards_mutex.promise()
        .then(function(mutex) {
            mutex.lock();
            let interest = $('#metanav-select-interest').val();
            let urlparams = allUrlParams();
            urlparams['event_id'] = $('#events').val();
            urlparams['awardee_id'] = $cell.attr('awardee_id');
            urlparams['was_picked_up'] = $cell.hasClass('picked_up');
            let url = `/admin/${interest}/_pickedup/rest` + '?' + setParams(urlparams);

            return $.post(url)
        })
        .then(function( json ) {
            if (json.error) {
                showerrorpopup(json.error);

            } else {
                let $checkbox = $cell.find('.awards-checkbox');
                if (json.picked_up) {
                    $cell.addClass('picked_up');
                    $checkbox.removeClass('unchecked-circle');
                    $checkbox.addClass('checked-circle');
                } else {
                    $cell.removeClass('picked_up');
                    $checkbox.removeClass('checked-circle');
                    $checkbox.addClass('unchecked-circle');
                }

                if (json.prev_picked_up) {
                    $cell.addClass('prev_picked_up');
                } else {
                    $cell.removeClass('prev_picked_up');
                }

            }
            awards_mutex.unlock();
        })
        .catch(function(e){
            // console.log('releasing lock due to exception');
            awards_mutex.unlock();
            throw e;
        });
}

function popup_note_dialog() {
    let $this = $(this);
    let $cell = $this.closest('.awards-cell');
    current_note_icon = $(this);

    // don't do anything if no awardee
    if (!$cell.attr('awardee_id')) {
        return
    }

    return awards_mutex.promise()
        .then(function(mutex) {
            mutex.lock();

            let interest = $('#metanav-select-interest').val();
            let urlparams = allUrlParams();
            urlparams['event_id'] = $('#events').val();
            urlparams['awardee_id'] = $cell.attr('awardee_id');
            let url = `/admin/${interest}/_notes/rest` + '?' + setParams(urlparams);

            return $.get(url)
        })
        .then(function( json ) {
            if (json.error) {
                showerrorpopup(json.error);

            } else {
                $('#awards-note-input').val(json.notes)
                $('#awards-note-container').css({
                    'display': 'inline-block',
                    'position': 'absolute', 
                    // Position relative to cell
                    'top': $cell.position().top + 5,
                    'left': $cell.position().left + 5,
                }).find('#awards-note-input').focus();
            }
            awards_mutex.unlock();
        })
        .catch(function(e){
            // console.log('releasing lock due to exception');
            awards_mutex.unlock();
            throw e;
        });

}

function save_note() {
    let $cell = current_note_icon.closest('.awards-cell');

    return awards_mutex.promise()
        .then(function(mutex) {
            mutex.lock();
            let interest = $('#metanav-select-interest').val();
            let urlparams = allUrlParams();
            urlparams['event_id'] = $('#events').val();
            urlparams['awardee_id'] = $cell.attr('awardee_id');
            urlparams['notes'] = $('#awards-note-input').val().trim();
            let url = `/admin/${interest}/_notes/rest` + '?' + setParams(urlparams);

            return $.post(url)
        })
        .then(function( json ) {
            if (json.error) {
                showerrorpopup(json.error);

            } else {
                let $notes = $cell.find('.awards-notes');
                if (json.notes) {
                    $notes.removeClass('add-comment');
                    $notes.addClass('insert-comment');
                    $notes.attr('title', json.notes);
                } else {
                    $notes.removeClass('insert-comment');
                    $notes.addClass('add-comment');
                    $notes.removeAttr('title');
                }

            }
            $('#awards-note-container').hide();
            awards_mutex.unlock();
        })
        .catch(function(e){
            // console.log('releasing lock due to exception');
            $('#awards-note-container').hide();
            awards_mutex.unlock();
            throw e;
        });
}

$(function() {
    let update_interval;

    $('#events').select2({
        placeholder: 'Select Event',
        // hide search box
        minimumResultsForSearch: -1,
    });

    $('#events').on('change', function() {
        divisions_rendered = false;
        if(update_interval) {
            stop_award_updates(update_interval);
        }
        update_interval = start_award_updates();
    });

    update_interval = start_award_updates();

    // this couples with $('.awards-notes').click( function where divisions are created
    $('#awards-save-note').click(save_note);

    $('#awards-note-input').on('keypress', function(event) {
        if (event.key === 'Enter') {
            $('#awards-save-note').click();
        }
    }).on('blur', function(event) {
        // Optional: Hide if clicking away, but ensure save button isn't the target
        if (!$(event.relatedTarget).is('#awards-save-note')) {
            $('#awards-note-container').hide();
        }
    });

})
