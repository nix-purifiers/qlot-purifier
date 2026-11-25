(sb-alien:define-alien-callable ("native_answer_cb" native-answer) sb-alien:unsigned-int
 ((value sb-alien:unsigned-int))
 (let ((bytes (make-array 64 :element-type '(unsigned-byte 8) :initial-element 0))
       (record (yason:parse (purifier-example:serialized))))
   (sb-ext:gc :full t)
   (ldb (byte 32 0) (+ value 1 (gethash "answer" record) (aref bytes 0)))))
