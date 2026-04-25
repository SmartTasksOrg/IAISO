<?php
/*
Plugin Name: IAIso Safety Guard
Description: Implementation of IAIso v5.0 Pressure Containment for WordPress.
*/
add_filter('wp_ai_output', function($content, $tokens) {
    $status = shell_exec("python3 -c 'from sdk.python.iaiso.engine import IAIsoEngine; print(IAIsoEngine().update_pressure(tokens=".$tokens."))'");
    return (trim($status) === "RELEASED") ? "Action Blocked: Safety Threshold." : $content;
}, 10, 2);
