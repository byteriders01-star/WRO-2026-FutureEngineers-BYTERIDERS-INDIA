def steering_command(heading_err, e_m, v, curvature):
    feed = math.atan(curvature * 1.0)      # predicted from track
    fb = math.atan2(0.75 * e_m, v + 0.1)   # stanley feedback
    return heading_err + 0.5 * feed + 0.5 * fb