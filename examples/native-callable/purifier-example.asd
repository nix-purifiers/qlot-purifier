(asdf:defsystem "purifier-example"
  :version "0.1.0"
  :depends-on ("yason")
  :serial t
  :components ((:file "example"))
  :in-order-to ((test-op (load-op "purifier-example")))
  :perform (test-op (operation component)
             (unless (search "\"answer\":42"
                             (uiop:symbol-call :purifier-example :serialized))
               (error "Locked JSON round trip failed"))))
