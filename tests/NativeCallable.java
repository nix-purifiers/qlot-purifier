import java.lang.foreign.*;
import static java.lang.foreign.ValueLayout.JAVA_INT;
class NativeCallable {
 public static void main(String[] args) throws Throwable {
  System.load(args[0]);
  int expected = Integer.parseInt(args[1]);
  var lookup = SymbolLookup.loaderLookup();
  var linker = Linker.nativeLinker();
  var init = linker.downcallHandle(lookup.find("native_init").orElseThrow(), FunctionDescriptor.of(JAVA_INT));
  if ((int)init.invokeExact() != 0) throw new AssertionError();
  var answer = linker.downcallHandle(lookup.find("native_answer").orElseThrow(), FunctionDescriptor.of(JAVA_INT, JAVA_INT));
  for (int i=0; i<100; i++) if ((int)answer.invokeExact(i) != i+expected) throw new AssertionError();
  if ((int)answer.invokeExact(-1) != expected-1) throw new AssertionError();
  System.out.println("Java FFM: 100 allocating callbacks, full GC and overflow PASS");
 }
}
