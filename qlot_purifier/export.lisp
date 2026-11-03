(dolist (dist (sort (copy-list (ql-dist:all-dists)) #'< :key #'ql-dist:preference))
  (format t "DIST~C~A~C~A~C~A~%" #\Tab (ql-dist:name dist) #\Tab
          (ql-dist:version dist) #\Tab (ql-dist:base-directory dist))
  (dolist (release (ql-dist:installed-releases dist))
    (format t "CAPTURE~C~A~C~A~C~A~C~A~%" #\Tab
            (ql-dist:name dist) #\Tab (ql-dist:name release) #\Tab
            (ql-dist:archive-url release) #\Tab
            (ql-dist:local-archive-file release))))
