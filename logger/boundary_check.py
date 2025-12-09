import numpy as np

def check_square_boundary_violation(robot_pos, waypoints, limit_dist=0.3):
    """
    Args:
        robot_pos: (x, y) tuple of the robot
        waypoints: List of 4 (x, y) tuples [W0, W1, W2, W3]
        limit_dist: Float, distance in meters defining the boundary width
    
    Returns:
        bool: True if boundary is violated (robot is far from ALL edges)
    """
    px, py = robot_pos
    
    # Close the loop: W0->W1, W1->W2, W2->W3, W3->W0
    # Create list of edges: [(W0, W1), (W1, W2)...]
    edges = []
    for i in range(len(waypoints)):
        p1 = waypoints[i]
        p2 = waypoints[(i + 1) % len(waypoints)] # Wrap around to 0
        edges.append((p1, p2))

    # Check distance to each edge
    # If the robot is within 'limit_dist' of ANY edge, it is safe.
    is_safe_on_any_edge = False

    for p1, p2 in edges:
        x1, y1 = p1
        x2, y2 = p2
        
        # 1. Calculate squared length of the edge segment
        seg_len_sq = (x2 - x1)**2 + (y2 - y1)**2
        
        if seg_len_sq == 0: continue # Avoid division by zero
        
        # 2. Project point onto the line segment to find the closest point
        # This prevents the infinite line problem (robot extending past the corner)
        t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / seg_len_sq
        
        # Clamp t to segment [0, 1] - essential for corners!
        t = max(0, min(1, t))
        
        closest_x = x1 + t * (x2 - x1)
        closest_y = y1 + t * (y2 - y1)
        
        # 3. Calculate Euclidean distance to that closest point
        dist = np.sqrt((px - closest_x)**2 + (py - closest_y)**2)
        
        # 4. Check against boundary
        if dist <= limit_dist:
            is_safe_on_any_edge = True
            break # Found a valid edge, no need to check others

    # If we finished the loop and strictly NEVER found a safe edge:
    return not is_safe_on_any_edge