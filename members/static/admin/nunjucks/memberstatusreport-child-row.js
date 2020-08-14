(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["memberstatusreport-child-row.njk"] = (function() {
function root(env, context, frame, runtime, cb) {
var lineno = 0;
var colno = 0;
var output = "";
try {
var parentTemplate = null;
if(runtime.contextOrFrameLookup(context, frame, "_showedit")) {
output += "\r\n    ";
output += "\r\n    ";
output += "\r\n    <div id=\"childrow-editform-\" class=\"childrow-editform\"></div>\r\n\r\n";
output += "\r\n";
;
}
else {
output += "\r\n    <div class=\"childrow-display\">\r\n        ";
if(runtime.contextOrFrameLookup(context, frame, "is_rsvp")) {
output += "\r\n            <div class=\"DTE_Field_Input\">";
output += runtime.suppressValue(env.getFilter("safe").call(context, runtime.contextOrFrameLookup(context, frame, "rsvp_response")), env.opts.autoescape);
output += "</div>\r\n        ";
;
}
else {
output += "\r\n            <div class=\"DTE_Label\"><b>Status Report</b></div>\r\n            <div class=\"DTE_Field_Input\">";
output += runtime.suppressValue(env.getFilter("safe").call(context, runtime.contextOrFrameLookup(context, frame, "statusreport")), env.opts.autoescape);
output += "</div>\r\n        ";
;
}
output += "\r\n    </div>\r\n";
;
}
output += "\r\n";
if(parentTemplate) {
parentTemplate.rootRenderFunc(env, context, frame, runtime, cb);
} else {
cb(null, output);
}
;
} catch (e) {
  cb(runtime.handleError(e, lineno, colno));
}
}
return {
root: root
};

})();
})();
